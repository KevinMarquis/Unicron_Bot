# importing packages
from pytube import YouTube
import os


def download(url):
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
    while os.path.exists(base + suffix + extension):
        suffix += str(i)
        i += 1
    new_file = base + suffix + extension

    os.rename(out_file, new_file)

    # result of success
    print(yt.title + " has been successfully downloaded.")
    print(base)
    filepath = os.path.join(destination, yt.title + suffix + extension)
    return filepath


if __name__ == "__main__":
    Link = str(input("Enter the URL of the video you want to download: \n>> "))
    download(Link)
