import asyncio
from urllib.parse import urljoin

import aiohttp
import requests
from tqdm import tqdm
import ptyprocess


class App:
    def __init__(self):
        self.headers = None
        self.m3u8_url = None
        self.data = []

    def get_html(self):
        self.headers = {
            'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) '
                          'Chrome/125.0.0.0 Safari/537.36 Edg/125.0.0.0'}
        r = requests.get(url=self.m3u8_url, headers=self.headers)
        return r.text

    def set_url(self, m3u8_url):
        self.m3u8_url = m3u8_url

    def get_data(self, html):
        ts_data_list = html.split('\n')
        for line in ts_data_list:
            if line.startswith('#'):
                continue
            else:
                if not '' == line:
                    self.data.append(urljoin(self.m3u8_url, line))

    def download_ts(self, path):
        async def async_download_ts(ts_url_num, ts_url, sen, t):
            async with sen:
                for i in range(1, 11):
                    try:
                        async with aiohttp.ClientSession() as session:
                            async with session.get(ts_url, headers=self.headers) as resp:
                                with open(f"{path}/{ts_url_num}.ts", 'wb') as f:
                                    f.write(await resp.content.read())
                                    f.close()
                                    t.update(1)
                                    print(ts_url)
                    except Exception as e:
                        print(f'重新下载第 {i} 次 {ts_url}')
                        continue

        async def async_run_download(data):
            tasks = []
            sen = asyncio.Semaphore(10)
            t = tqdm(total=len(data), desc="Processing")
            for ts_url_num in range(1, len(data) + 1):
                task = asyncio.create_task(async_download_ts(ts_url_num, data[ts_url_num - 1], sen, t))
                tasks.append(task)
            await asyncio.wait(tasks)

        loop = asyncio.get_event_loop()
        loop.run_until_complete(async_run_download(self.data))

    def merge_mp4_mac(self, file_name):
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

        # 定义要运行的命令
        result = run_zd(command=['pwd'])
        file = ''
        for i in range(1, len(self.data)+1):
        # for i in range(1, 240+1):
            file_line = f'file {result}/data/ts文件/{i}.ts\n'
            file = file + file_line
        with open(f"{result}/data/ts文件/filelist.txt", 'w') as f:
            f.write(file)
            f.close()
        command = f'ffmpeg -f concat -safe 0 -i {result}/data/ts文件/filelist.txt -c copy {result}/data/{file_name}'
        run_zd(command=command)
        run_zd(command=f'rm -rf {result}/data/ts文件/*')

    def main(self, file_name):
        html = self.get_html()
        self.get_data(html)
        self.download_ts(path='./data/ts文件')
        self.merge_mp4_mac(file_name)


if __name__ == '__main__':
    url = 'https://i.hlscf.top/20240323/5be30198a9417be17def63009301e25e/hls/index.m3u8'
    file_name = '2.mp4'
    app = App()
    app.set_url(url)
    app.main(file_name)
