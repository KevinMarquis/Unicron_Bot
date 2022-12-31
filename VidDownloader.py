# importing packages
from pytube import YouTube
import os

def download(url):
    """Downloads the video at the passed url.  Returns a tuple containing the file path and video name."""
    yt = YouTube(str(url))
    video = yt.streams.filter(only_audio=True).first()

    dir_path = os.path.dirname(os.path.realpath(__file__))
    path = dir_path + "\\MusicQueue"
    # Check whether the specified path exists or not
    isExist = os.path.exists(path)
    if not isExist:
        os.makedirs(path)

    # check for destination to save file
    #print("Enter the destination (leave blank for current directory)")
    destination = path

    # download the file
    out_file = video.download(output_path=destination)

    # save the file
    base, ext = os.path.splitext(out_file)
    extension = '.mp3'
    suffix = ""
    i = 1
    while os.path.exists(path + "\\AUDIO" + suffix + extension):
        i += 1
        suffix = str(i)

    new_file = path + "\\AUDIO" + suffix + extension
    os.rename(out_file, new_file)

    # result of success
    print(yt.title + " has been successfully downloaded.")
    filepath = os.path.join(destination, "AUDIO" + suffix + extension)
    VideoName = base[len(path) + 1:]
    return (filepath, VideoName)

def downloadHERALD(url):  # Yeah, we reuse a lot of code here, but I don't really feel like fixing the function right now.
    """Downloads the video at the passed url.  Returns a tuple containing the file path and video name."""
    yt = YouTube(str(url))
    video = yt.streams.filter(only_audio=True).first()

    dir_path = os.path.dirname(os.path.realpath(__file__))
    path = dir_path + "\\HeraldProfiles"
    # Check whether the specified path exists or not
    isExist = os.path.exists(path)
    if not isExist:
        os.makedirs(path)

    # check for destination to save file
    destination = path

    # download the file
    out_file = video.download(output_path=destination)

    # save the file
    base, ext = os.path.splitext(out_file)
    extension = '.mp3'
    suffix = ""
    i = 1
    while os.path.exists(base + suffix + extension):
        i += 1
        suffix = str(i)
    new_file = base + suffix + extension

    os.rename(out_file, new_file)

    # result of success
    print(yt.title + " has been successfully downloaded.")
    filepath = os.path.join(destination, yt.title + suffix + extension)
    VideoName = base[len(path) + 1:]
    return (filepath, VideoName)


if __name__ == "__main__":
    Link = str(input("Enter the URL of the video you want to download: \n>> "))
    try:
        download(Link)
    except Exception as e:
        print(e)
