import argparse
from ast import arg
import os
import hashlib
import time
import json
import signal
import configparser
from concurrent.futures import ProcessPoolExecutor, ThreadPoolExecutor
from urllib import request


def HiddfFileUpdate(hiddf_file: dict, idx: int):
    """
    :param hiddf_file: 包含被更新文件信息的字典
    :param idx: 当前被更新文件的序号
    :return:
    """
    os.system('hpatchz -f "{}/{}" "{}/{}{}" "{}/{}" >> hdiff_log.txt'.format(root, hiddf_file["remoteName"],
                                                                             root, hiddf_file["remoteName"], ".hdiff",
                                                                             root, hiddf_file["remoteName"]))
    os.remove("{}/{}{}".format(root, hiddf_file["remoteName"], ".hdiff"))
    print('[{}/{}] 已更新 {}'.format(idx + 1, HiddfFileLen, hiddf_file["remoteName"]))


def Update(UpdatePatchName: str):
    """
    :param UpdatePatchName: 补丁包的文件名
    :return:
    """
    # 解压整个游戏本体补丁
    print("\n解压资源文件......")
    os.system('7z.exe x "{}/{}" -o"{}" -y'.format(root, UpdatePatchName, root))
    # 删除文件
    if os.path.exists("{}/deletefiles.txt".format(root)):
        print("\n")
        with open("{}/deletefiles.txt".format(root), encoding="utf-8") as f:
            for delete_file in f:
                delete_file = delete_file.rstrip()
                try:
                    os.remove("{}/{}".format(root, delete_file))
                    print("已删除 {}".format(delete_file))
                except Exception:
                    print("删除失败 {}".format(delete_file))
        os.remove('{}/deletefiles.txt'.format(root))
    # 更新文件
    try:
        with open('{}/hdifffiles.txt'.format(root), encoding="utf-8") as f:
            HiddfFileList = []
            for hiddf_file in f:
                HiddfFileList.append(eval(hiddf_file.rstrip()))  # 执行一个字符串表达式,此处将字符串转成字典
        global HiddfFileLen
        HiddfFileLen = len(HiddfFileList)
        print('\n更新资源文件......\n')
        pool = ProcessPoolExecutor(max_workers=5)
        for idx, x in enumerate(HiddfFileList):
            pool.submit(HiddfFileUpdate(x, idx))
        pool.shutdown()
        os.remove('{}/hdifffiles.txt'.format(root))
        os.remove("hdiff_log.txt")
    except FileNotFoundError:  # b服sdk压缩包里面没有hdifffiles.txt, 只要解压了压缩包就行
        pass


def CheckFileMD5(FileDict: dict, idx: int):
    """
    :param FileDict:包含被检查文件信息的字典
    :param idx:当前被检查文件的序号
    :return:
    """
    m = hashlib.md5()  # 创建md5对象
    try:
        with open('{}/{}'.format(root, FileDict["remoteName"]), 'rb') as f2:
            while True:
                data = f2.read(2048)
                if not data:
                    break
                m.update(data)  # 更新md5对象
                md5 = m.hexdigest()  # 返回md5对象
        if FileDict['md5'] == md5:
            print('[{}/{}] {} 校验通过！'.format(idx + 1, CheckFileLen, FileDict['remoteName']))
        else:
            print("\033[1;31m" + "[{}/{}] {} 校验失败！计算值 {},原值 {}".format(idx + 1, CheckFileLen,
                                                                       FileDict['remoteName'], md5,
                                                                       FileDict['md5']) + "\033[0m")
            print("\033[1;31m" + "资源文件校验失败,更新可能出现异常,可能需要重新下载游戏！" + "\033[0m")
    except Exception:
        print("\033[1;31m" + "[{}/{}] {} 打开文件失败！".format(idx + 1, CheckFileLen, FileDict['remoteName']) + "\033[0m")
        print("\033[1;31m" + "资源文件校验失败,更新可能出现异常,可能需要重新下载游戏！" + "\033[0m")


def StartCheckMD5(pkg_version: list):
    """
    :param pkg_version: 包含各个文件md5值的文件
    :return: None
    """
    print('\n')
    global CheckFileLen
    CheckFileList = []
    for pkg in pkg_version:
        # 读取文件
        with open("{}/{}".format(root, pkg), "r", encoding="utf-8") as f1:
            for key in f1:
                CheckFileList.append(eval(key))
    # 用于显示进度
    CheckFileLen = len(CheckFileList)
    # 使用多进程进行校验文件md5
    pool = ProcessPoolExecutor(max_workers=5)
    for idx, x in enumerate(CheckFileList):
        pool.submit(CheckFileMD5(x, idx))
    pool.shutdown()


def StartUpdate(Patch: list):
    """
    :param Patch: 包含补丁包文件名的列表
    :return:
    """
    StartTime = time.time()
    # 更新游戏
    for PatchName in Patch:
        Update(PatchName)
    print("\n")
    EndUpdateTime = time.time()
    # 校验文件
    if IsCheckMd5:
        PkgVersion = []
        for file in os.listdir(root):
            if "pkg" in file:
                print("已找到资源校验文件 ", file)
                PkgVersion.append(file)
        StartCheckMD5(PkgVersion)
    # 移除更新补丁
    for PatchName in Patch:
        os.remove("{}/{}".format(root, PatchName))
    print("\nFinish!")
    EndTime = time.time()
    UpdateDelta = EndUpdateTime - StartTime
    CheckMD5Delta = EndTime - EndUpdateTime
    SumDelta = EndTime - StartTime
    print(f'更新耗时: {UpdateDelta:.1f} 秒')
    print(f'校验耗时: {CheckMD5Delta:.1f} 秒')
    print(f'总计耗时: {SumDelta:.1f} 秒')




def GetPatch(PatchContent: dict, IsPre: bool):
    """
    ----------------------对照api返回的json来看代码---------------------
    用于读取api返回的json数据里的补丁包链接,判断本地需要的补丁包,缺少会下载
    最后会返回补丁包的文件名和B服SDK的版本号{没有下载SDK的话返回None)
    :param PatchContent: api返回的json数据{只需要json数据内“data”那部分的内容)
    :param IsPre:如果是预更新设置为True,正常更新是False
    :return: 已经下载好的补丁包文件名{list)和B服SDK版本号{str)
    """
    # 用于判断是否需要下载补丁的标志
    NeedDownload = False
    # 预下载跟普通更新的补丁包链接所在对应的key是不一样的
    if IsPre:
        Content = PatchContent["pre_download_game"]
    else:
        Content = PatchContent["game"]
    # 游戏更新一般最多可以跨一个版本更新
    # 如最新为2.8,2.6和2.7都可以升到2.8
    # 所以diffs是一个列表,里面有两个版本的补丁包
    # 生成的这个临时字典可以知道diffs列表中每项是适用与那个版本的游戏客户端
    temp = {}
    # 生成的字典类似 {“2.7.0":0,"2.6.0":1}
    # 说明用于2.7版本的补丁包链接在diffs的第一项{diffs[0]),以此类推
    for idx, item in enumerate(Content["diffs"]):
        temp[item["version"]] = idx
    # 如果当前游戏版本不在生成temp的keys里面,说明版本过低,没有对应的补丁包用于更新
    if NowVersion not in temp.keys():
        print("当前版本过低,需要重新下载游戏！")
        exit()
    # 先把游戏本体的补丁包链接加入到list
    DownloadUrl = [Content["diffs"][temp[NowVersion]]["path"]]
    # 下面两个字典与上面temp字典的作用类似
    Game = {
        "pcadbdpz": "YuanShen",
        "bilibili": "YuanShen",
        "mihoyo": "GenshinImpact"
    }
    Voice = {
        "Chinese": 0,
        "English(US)": 1,
        "Japanese": 2,
        "Korean": 3
    }
    # 将语音包补丁链接加入到list
    for i in Voice.keys():
        # 本地游戏客户端语言包所在的路径
        VoicePath = "{}/{}_Data/StreamingAssets/Audio/GeneratedSoundBanks/Windows/{}".format(root, Game[Server], i)
        if os.path.exists(VoicePath):
            DownloadUrl.append(Content["diffs"][temp[NowVersion]]["voice_packs"][Voice[i]]["path"])
    # 如果是B服,顺便将SDK一起下载{无论是否有更新)
    if Server == "bilibili":
        DownloadUrl.append(PatchContent["sdk"]["path"])
        BilibiliSdkVersion = PatchContent["sdk"]["version"]
    else:
        BilibiliSdkVersion = None
    # 到此就知道需要本地游戏客户端需要那些补丁
    # result里面就是需要的补丁文件名
    result = [i.split("/")[-1] for i in DownloadUrl]
    print("目前需要的更新补丁有\n" + "\n".join(result))
    # 判断补丁是否下载完成
    # 如果没有下载或者未完成下载就会设置NeedDownload为True,然后进行下载
    for i in result:
        if os.path.exists("{}/{}".format(root, i + ".aria2")):
            print("更新补丁 {} 未下载完成,继续下载！".format(i))
            NeedDownload = True
        if not os.path.exists("{}/{}".format(root, i)):
            print("更新补丁 {} 未下载,开始下载".format(i))
            NeedDownload = True
    if NeedDownload:
        DownloadCommand = 'aria2c -s 32 --file-allocation none -c -j 10 -x 16 -d "{}" -Z '.format(root) + " ".join(
            DownloadUrl)
        os.system(DownloadCommand)
    return result, BilibiliSdkVersion


def SignalExit(signum, frame):
    print("\n你选择了中断程序\n")
    exit()


def main():
    global cfg, Server, NowVersion, NewVersion, BilibiliSdkVersion
    # 获取游戏更新补丁的api
    PatchUrl = {
        "cn": "https://sdk-static.mihoyo.com/hk4e_cn/mdk/launcher/api/resource?channel_id=1&key=eYd89JmJ&launcher_id=18&sub_channel_id=1",
        "bilibili": "https://sdk-static.mihoyo.com/hk4e_cn/mdk/launcher/api/resource?key=KAtdSsoQ&launcher_id=17&channel_id=14",
        "os": "https://sdk-os-static.mihoyo.com/hk4e_global/mdk/launcher/api/resource?channel_id=1&key=gcStgarh&launcher_id=10&sub_channel_id=0"
    }
    # 读取游戏根目录下的config.ini来获取游戏版本号以及游戏服务器
    if not os.path.exists("{}/config.ini".format(root)):
        print("无法读取游戏根目录下的config.ini,请检查路径是否正确")
        exit()
    cfg = configparser.ConfigParser()
    cfg.read("{}/config.ini".format(root))
    Server = cfg.get("General", "cps")

    # # =========================================================================
    # NowVersion = "2.8.0"
    # with open("url/2.8.0_os_pre.json", "r", encoding="utf-8") as f:
    #     Content = json.load(f)
    # # =========================================================================

    # =========================================================================
    NowVersion = cfg.get("General", "game_version")
    url = ""
    if Server == "pcadbdpz":
        print("当前游戏服务器为国服")
        url = PatchUrl["cn"]
    elif Server == "bilibili":
        print("当前游戏服务器为B服")
        url = PatchUrl["bilibili"]
    elif Server == "mihoyo":
        print("当前游戏服务器为国际服")
        url = PatchUrl["os"]
    else:
        print("无法获取当前游戏服务器类型")
        exit()
    headers = {
        "user-agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/95.0.4638.54 Safari/537.36"
    }
    Req = request.Request(url=url, headers=headers)
    Response = request.urlopen(Req)
    Content = Response.read().decode("utf8")
    Content = json.loads(Content)
    # =========================================================================
    
    PatchContent = Content["data"]
    # 判断是否有预下载,有预下载直接下载好补丁
    if PatchContent["pre_download_game"] is not None:
        PreVersion = PatchContent["pre_download_game"]["latest"]["version"]
        print("当前版本为{},目前有预更新,预更新版本为{} ".format(NowVersion, PreVersion))
        GetPatch(PatchContent, IsPre=True)
        print("\n预更新下载完成！")
    else:
        # 没有预下载直接检查更新
        NewVersion = PatchContent["game"]["latest"]["version"]
        if NowVersion == NewVersion:
            print("当前版本为最新版本！")
        else:
            print("当前版本为 {} , 官方最新版本为 {}".format(NowVersion, NewVersion))
            # 检查是否下载好补丁,没有补丁会进行下载
            Patch, BilibiliSdkVersion = GetPatch(PatchContent, IsPre=False)
            print("\n更新补丁已下载完成,按下回车开始更新游戏\n")
            # input()
            print("\033[1;31m" + "----------游戏更新过程中请不要中断程序！！！---------" + "\033[0m")
            StartUpdate(Patch)
    # =========================================================================
            # 修改config文件
            cfg.set("General", "game_version", NewVersion)
            if Server == "bilibili":
                cfg.set("General", "plugin_sdk_version", BilibiliSdkVersion)
            with open("{}/config.ini".format(root), "w") as f:
                cfg.write(f)
    # =========================================================================

if __name__ == "__main__":
    signal.signal(signal.SIGINT, SignalExit)
    signal.signal(signal.SIGTERM, SignalExit)
    parser = argparse.ArgumentParser(description="")
    parser.add_argument('--GamePath', '-p', default='D:/Genshin Impact/Genshin Impact Game', type=str)
    parser.add_argument('--IsCheckMd5', '-i', default=True, type=bool)
    args = parser.parse_args()
    root = args.GamePath
    IsCheckMd5 = args.IsCheckMd5
    # =========================================================================
    main()
    # =========================================================================
    # Patch = ["game_3.0.0_3.1.0_hdiff_3dlivNRan0Dq7ykP.zip","zh-cn_3.0.0_3.1.0_hdiff_pkNHKFGT9oVOc7IX.zip"]
    # StartUpdate(Patch=Patch)
