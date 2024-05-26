"""
    #整体步骤=>         http://yhdm63.com/mov/91973/1.html
    1.获取播放线路的请求url
    2.生成 所有播放线路中的ts下载文件的json文件  （包含提取ts文件的下载路径）
    3.下载
    4.判别是否需要解密
    5.如果需要解密，拿到秘钥
    6.解密
    7.根M3U8的正确顺序来合并所有的tS义件=>MP4
"""
import asyncio
import json
import os
import shutil
import subprocess
from time import sleep
from urllib.parse import urljoin

import aiofiles
import aiohttp
import requests
from lxml import etree
from Crypto.Cipher import AES  # 需要安装 PyCrypto   pip install pycryptodome
from tqdm import tqdm

MIAN_HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/123.0.0.0 Safari/537.36 Edg/123.0.0.0"
}


def produce_play_line_js(film_name, play_line_url):
    """
    生成 播放线路原js文件
    :param film_name: 影片名
    :param play_line_url: 播放线路的js文件的URL
    :return: None
    """
    text = requests_get(url=play_line_url, headers=MIAN_HEADERS).text.replace(';', ';\n')
    # 判断文件夹是否存在 不存在就创建
    if not os.path.exists(f'./data/{film_name}'):
        os.makedirs(f'./data/{film_name}')
    with open(f'./data/{film_name}/play_line_list.js', 'w', encoding='utf-8') as f:
        f.write(text)
        # print("已生成      /data/play_line_list.js")


def get_cache_file(line_name):
    """
    获取 m3u8缓存文件
    :param line_name: 文件名
    :return: 将文件以 "行" 组成的列表
    """
    with open(f'./data/缓存文件/{line_name}.txt', 'r', encoding='utf-8') as f:
        return f.readlines()


def get_json_iv(line):
    """
    判断是否有 iv 参数
    :param line: 字符串
    :return: 有则返回参数 无则返回None
    """
    if 'IV=' in line:
        return line.split('IV=')[-1].strip()
    else:
        return None


def get_ext_x_key(line_name, line_m3u8_url):
    """
    判断是否有加密
    :param line_name: 播放线路  别名
    :param line_m3u8_url: 播放线路  url
    :return: 有加密返回{METHOD:'',URI:'',IV:''} 反之返回 None
    """
    # 获取 m3u8缓存文件
    for line in get_cache_file(line_name):
        if "EXT-X-KEY" in line:
            # print(line)
            # print(line.split('"'))
            try:
                return {
                    'method': line.split(',')[0].split('=')[-1],
                    'uri': urljoin(line_m3u8_url, line.split('"')[1]),
                    'iv': get_json_iv(line),
                }
            except Exception as e:
                print('!!!!!!!密钥获取失败!!!!!!!', e, end='')
                return "密钥获取失败"
    else:
        return None


def requests_get(url, headers=None):
    """
    封装 requests get方法
    :param url: 请求链接
    :param headers: 请求头
    :return: 返回请求数据
    """
    try:
        return requests.get(url=url, headers=headers)
    except Exception as e:
        print(f"访问失败   {url}  ", e, end='')


def produce_m3u8_file(line_name, line_m3u8_url):
    """
    生成 m3u8缓存文件
    :param line_name: 播放线路 别名
    :param line_m3u8_url: 包含ts片段下载url的 m3u8链接
    :return: None
    """
    with open(f'./data/缓存文件/{line_name}.txt', 'w', encoding='utf-8') as f1:
        try:
            f1.write(requests_get(url=line_m3u8_url, headers=MIAN_HEADERS).text)
        except Exception as e:
            print(f'生成缓存文件失败     {line_name}', e, end='')

    # 判断有无第二次访问 EXT-X-STREAM-INF
    mark = False
    with open(f'./data/缓存文件/{line_name}.txt', 'r', encoding='utf-8') as f2:
        lines = f2.readlines()
        for line in lines:
            if 'EXT-X-STREAM-INF' in line:
                mark = True
                break
        if mark:
            # 进行第二次解析
            for line in lines:
                if line.startswith('#'):
                    continue
                line_m3u8_url = urljoin(line_m3u8_url, line.strip())

    with open(f'./data/缓存文件/{line_name}.txt', 'w', encoding='utf-8') as f3:
        try:
            text = requests_get(url=line_m3u8_url, headers=MIAN_HEADERS).text

        except Exception as e:
            text = '获取内容失败'
            print(f"获取内容失败   {line_m3u8_url}", e, end='')
        f3.write(text)


def get_effective(param):
    """
    # 判断片段是否有效
    :param param: 测试url
    :return: 有效为True 反之同理
    """
    try:
        r = requests_get(url=param, headers=MIAN_HEADERS)
        if r.status_code == 200:
            try:
                with open(param.split('/')[-1], 'wb') as f:
                    f.write(r.content)
                os.remove(param.split('/')[-1])
                return True
            except:
                return False
        else:
            return False
    except Exception as e:
        print(f'测试影片失败       {param}', e, end='')
        return False


def produce_play_line_json(film_name, line_m3u8_url):
    """
    生成播放线路.json文件
    :param film_name: 影片名
    :param play_line_url: 播放线路的js文件的URL
    :return: 返回dict => {line_name：{line_name：line_m3u8_url}}
    """
    play_line_json = {}
    try:
        os.mkdir(f'./data/{film_name}')
    except FileExistsError:
        pass
    # 分析原js文件 提取真正的m3u8链接
    print(f'解析m3u8     ========>>     ', end='')

    # 生成 m3u8缓存文件
    produce_m3u8_file(film_name, line_m3u8_url)

    # 获取 下载url的ts片段
    m3u8_ts = get_m3u8_ts(film_name, line_m3u8_url)
    play_line_json[film_name] = {
        'line_name': film_name,
        'effective': get_effective(m3u8_ts[0]),  # 判断片段是否有效
        'ext_x_key': get_ext_x_key(film_name, line_m3u8_url),  # 判断是否有加密
        'm3u8_ts_urls': m3u8_ts,
    }
    print('解析完毕')
    # 生成 播放线路的json文件
    if os.path.exists(f'./data/{film_name}/play_line_dict.json'):
        if str(input('play_line_dict.json  已存在 是否覆盖（0为不覆盖，任意输入为覆盖）：')) != '0':
            with open(f'./data/{film_name}/play_line_dict.json', 'w', encoding='utf-8') as f2:
                json.dump(play_line_json, f2, ensure_ascii=False)
                print("已生成      /data/play_line_dict.json")
        else:
            print('已取消覆盖文件      /data/play_line_dict.json')
    else:
        with open(f'./data/{film_name}/play_line_dict.json', 'w', encoding='utf-8') as f2:
            json.dump(play_line_json, f2, ensure_ascii=False)
            print("已生成      /data/play_line_dict.json")
    return play_line_json


def get_m3u8_ts(line_name, line_m3u8_url):
    """
    获取 下载url的ts片段
    :param line_name: 播放线路  别名
    :param line_m3u8_url: 播放线路  url
    :return: ts片段下载urls
    """
    # 获取 m3u8缓存文件
    m3u8_url_list = []
    for line in get_cache_file(line_name):
        if line.startswith('#'):
            continue
        m3u8_url_list.append(urljoin(line_m3u8_url, line.strip()))
    return m3u8_url_list


def download_play_line(url):
    """
    获取播放列表
    :param url: 当前播放网页url
    :return: film_name => 影片名, play_line_url => 播放列表的 js文件url
    """
    # 第一次解析出播放线路         "http://test.gqyy8.com:8077/ne2/s91973.js" => 播放线路网址
    requ = requests_get(url=url, headers=MIAN_HEADERS)
    tree = etree.HTML(requ.text)
    film_name = tree.xpath('//div[@class="h2"]/a[3]/text()')[0]
    play_line_url = tree.xpath('/html[1]/script[@type="text/javascript"]/@src')[0]

    # 解析播放线路文件 生成json文件
    return str(film_name).strip().replace(' ', ''), play_line_url


def get_play_line_dict(film_name):
    with open(f'./data/{film_name}/play_line_dict.json', 'r', encoding='utf-8') as f:
        loads = json.load(f)
        return loads


def analysis_film(MAIN_URL):
    """
    解析影片  （播放线路、ts下载地址、密钥）
    :param MAIN_URL: 影片url
    :return: film_name 影片名
    """
    # 1.获取播放线路的请求url
    film_name, play_line_url = download_play_line(MAIN_URL)

    # 2.生成 包含所有播放线路的json文件  （包含提取ts文件的下载路径）


    return film_name


def get_film_ts_list_and_exr_x_key(film_name):
    """
    读取本地保存下载ts列表
    :return: 返回 ts列表 , exr_x_key
    """
    # 1、获取本地文件
    play_line_dict = get_play_line_dict(film_name)
    # 2、获取影片资源
    for play_line in play_line_dict.keys():
        # 3、判断影片是否有效
        if play_line_dict[play_line]['effective']:
            # 4、判断影片是否有加密
            if not play_line_dict[play_line]['ext_x_key'] is None:
                ext_x_key = play_line_dict[play_line]['ext_x_key']
                return play_line_dict[play_line]['m3u8_ts_urls'], ext_x_key
            else:
                return play_line_dict[play_line]['m3u8_ts_urls'], None


async def async_download_ts(film_name, ts, sem, progress_bar):
    """
    下载单个ts片段
    :param progress_bar: tqdm 信号
    :param film_name: 影片名
    :param ts: ts片段
    :param sem: 信号量
    :return:
    """
    async with sem:
        # 判断文件夹是否存在 不存在就创建
        if not os.path.exists(f'./data/{film_name}/ts文件/解密前'):
            os.makedirs(f'./data/{film_name}/ts文件/解密前')

        # print(f"开始下载   {ts}")
        for i in range(10):
            try:
                async with aiohttp.ClientSession() as session:
                    async with session.get(url=ts, headers=MIAN_HEADERS) as reqs:
                        if reqs.status == 200:
                            content = await reqs.content.read()
                            async with aiofiles.open(f'./data/{film_name}/ts文件/解密前/{str(ts).split("/")[-1]}',
                                                     'wb') as f:
                                await f.write(content)
                                # print(f"下载完成     {ts}")
                                progress_bar.update(1)
                                break
                        else:
                            print(f"下载失败：HTTP 状态码 {reqs.status}")
            except Exception as e:
                print(f'下载失败,进行重新下载(第{i + 1}次)        {ts}', e)


async def async_download_film(film_name, ts_list):
    """
    协程下载ts文件
    :param film_name: 影片名
    :param ts_list: ts文件
    :return: None
    """
    print(f'############  影片({film_name})开始下载  ############')
    sem = asyncio.Semaphore(100)
    tasks = []
    progress_bar = tqdm(total=len(ts_list), desc="Processing")
    for ts in ts_list:
        t = asyncio.create_task(async_download_ts(film_name, ts, sem, progress_bar))
        tasks.append(t)
    await asyncio.wait(tasks)
    progress_bar.close()
    print(f'############  影片({film_name})下载完成  ############')


def download_ts(film_name):
    """
    下载影片 使用协程技术
    :param film_name: 影片名
    :return: ts_list ==> ts列表, key ==> EXT-X-KEY
    """
    # 1、读取本地保存下载ts列表
    ts_list, exr_x_key = get_film_ts_list_and_exr_x_key(film_name)
    # 2、使用协程下载资源
    if 下载文件:
        loop = asyncio.get_event_loop()
        loop.run_until_complete(async_download_film(film_name, ts_list))

    return ts_list, exr_x_key


def get_key(exr_x_key):
    """
    拿 uri 密钥
    :param exr_x_key: EXT-X-KEY
    :return:
    """
    return requests_get(exr_x_key['uri'], headers=MIAN_HEADERS).content


async def desc_one(sem, ts_path, new_ts_path, uri, iv):
    """
    解密单个ts文件
    :param sem: 信息量
    :param ts_path: 解密前 ts文件位置
    :param new_ts_path: 解密后 ts文件位置
    :param uri: 密钥
    :param iv: AEC_CBC解密需要的iv
    :return: None
    """
    async with sem:
        # 解密
        print(f"开始解密        {ts_path}")
        async with (aiofiles.open(ts_path, 'rb') as f1,
                    aiofiles.open(new_ts_path, 'wb') as f2):
            content = await f1.read()
            # 解密
            if iv is None:
                aes = AES.new(key=uri, mode=AES.MODE_CBC, IV=b"0000000000000000")
            else:
                aes = AES.new(key=uri, mode=AES.MODE_CBC, IV=bytes.fromhex(iv[2:]))
            new_content = aes.decrypt(content)
            await f2.write(new_content)
        print(f"解密完成        {new_ts_path}")


async def async_desc_all(film_name, ts_list, uri, iv):
    """
    协程解密所有文件
    :param film_name: 影片名
    :param ts_list: ts列表
    :param uri: 密钥
    :param iv: AEC_CBC解密需要的iv
    :return: None
    """

    sem = asyncio.Semaphore(100)
    tasks = []
    for ts in ts_list:
        ts_name = str(ts).split('/')[-1]
        ts_path = f'./data/{film_name}/ts文件/解密前/{ts_name}'
        new_ts_path = f'./data/{film_name}/ts文件/解密后/{ts_name}'
        task = asyncio.create_task(desc_one(sem, ts_path, new_ts_path, uri, iv))
        tasks.append(task)
    await asyncio.wait(tasks)


def get_iv(exr_x_key):
    """
    拿 AEC_CBC解密需要的iv
    :param exr_x_key: EXT-X-KEY
    :return:
    """
    return exr_x_key['iv']


def move_files(source_folder, destination_folder):
    # 确保目标文件夹存在，如果不存在则创建
    if not os.path.exists(destination_folder):
        os.makedirs(destination_folder)

    # 遍历源文件夹中的所有文件
    for filename in os.listdir(source_folder):
        source_file_path = os.path.join(source_folder, filename)
        destination_file_path = os.path.join(destination_folder, filename)

        # 如果是文件，则移动到目标文件夹
        if os.path.isfile(source_file_path):
            shutil.move(source_file_path, destination_file_path)
            # print(f"Moved {filename} to {destination_folder}")
        # 如果是文件夹，则递归调用move_files函数移动文件夹内的文件
        elif os.path.isdir(source_file_path):
            move_files(source_file_path, destination_file_path)


def untie_key(film_name, ts_list, exr_x_key):
    """
    解密
    :param ts_list: ts 列表
    :param film_name: 影片名
    :param exr_x_key: 密钥
    :return: None
    """
    # 判断文件夹是否存在 不存在就创建
    if not os.path.exists(f'./data/{film_name}/ts文件/解密后'):
        os.makedirs(f'./data/{film_name}/ts文件/解密后')
    # 1、判断是否有密钥
    if exr_x_key is None:
        move_files(f'./data/{film_name}/ts文件/解密前', f'./data/{film_name}/ts文件/解密后')
        return None

    # 2、开始解密
    print(f'############    开始解密({film_name})    ############')
    loop = asyncio.get_event_loop()
    loop.run_until_complete(async_desc_all(film_name, ts_list, get_key(exr_x_key), get_iv(exr_x_key)))
    print(f'############    解密完成({film_name})    ############')


def copy_file(source_path, destination_path):
    try:
        shutil.copyfile(source_path, destination_path)
        print(f"文件从 {source_path} 复制到 {destination_path} 成功！")
    except FileNotFoundError:
        print("文件不存在，请检查路径。")
    except PermissionError:
        print("权限错误，无法复制文件。")
def run_zd(command):
    import subprocess

    # 定义要运行的命令

    # 运行命令
    process = subprocess.Popen(command, shell=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)

    # 等待命令执行完成
    stdout, stderr = process.communicate()

    # 打印输出结果
    result = stdout.decode()
    if process.returncode != 0:
        print("Error:", stderr.decode())
    return result.replace('\n', '')

def merge_mp4_mac(file_name, path, data):
    # 定义要运行的命令
    result = run_zd(command=['pwd'])
    file = ''
    for i in range(1, len(data) + 1):
        file_name_ = str(data[i-1]).split('/')[-1]
        file_line = f'file {result}{path}/ts文件/解密后/{file_name_}\n'
        file = file + file_line
    with open(f"{result}{path}/ts文件/解密后/filelist.txt", 'w') as f:
        f.write(file)
        f.close()
    command = f'ffmpeg -f concat -safe 0 -i {result}{path}/ts文件/解密后/filelist.txt -c copy {result}{path}/{file_name}.mp4'
    run_zd(command=command)
    run_zd(command=f'rm -rf {result}{path}/ts文件')
    run_zd(command=f'rm -rf {result}{path}/play_line_dict.json')



def download_film(film_name, MAIN_URL):
    """
    下载影片
    :param MAIN_URL: 影片播放网址
    :return: None
    """
    # 1、解析影片  （播放线路、ts下载地址、密钥）
    if 加载js文件:
        produce_play_line_json(film_name, MAIN_URL)
    # 2.下载
    ts_list, exr_x_key = download_ts(film_name=film_name)

    # # 3.解密
    untie_key(film_name=film_name, ts_list=ts_list, exr_x_key=exr_x_key)

    # 4.根M3U8的正确顺序来合并所有的tS义件=>MP4
    merge_mp4_mac(film_name, path=f'/data/{film_name}', data=ts_list)


加载js文件 = True
下载文件 = True

if __name__ == '__main__':
    MAIN_URL = 'https://bspbf.649328.com/exclusive/2024-05-25/5c03b7d209b3e206ef264622e58fc0381715930369530-9c8c64f068d94c4481349c15891d704c/index.m3u8'
    download_film('扩张骚穴无套内射', MAIN_URL)
