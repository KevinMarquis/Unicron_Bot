# importing packages
from pytube import YouTube
import os

def download(url):
    yt = YouTube(str(url))
    video = yt.streams.filter(only_audio=True).first()

    # check for destination to save file
    print("Enter the destination (leave blank for current directory)")
    destination = '.'

    # download the file
    out_file = video.download(output_path=destination)

    # save the file
    base, ext = os.path.splitext(out_file)
    #new_file = base + '.mp3'
    new_file = "MUSIC.mp3"  #TODO: Need to make different names for music files
    #TODO: Idea: maybe create a folder for music files, name them by # ex, 1, 2, 3, 4, etc... Wipe out folder when it exceeds 10 or so - that folder will be used as a queue.
    os.rename(out_file, new_file)

    # result of success
    print(yt.title + " has been successfully downloaded.")
    return new_file


if __name__ == "__main__":
    Link = str(input("Enter the URL of the video you want to download: \n>> "))
    download(Link)