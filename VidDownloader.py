# importing packages
from pytube import YouTube
import os

def download(url):
    """Downloads the video at the passed url.  Returns a tuple containing the file path and video name."""
    yt = YouTube(str(url))
    video = yt.streams.filter(only_audio=True).first()

    Folder = "MusicQueue"
    # Check whether the specified path exists or not
    if not os.path.exists(Folder):
        os.makedirs(Folder)

    # check for destination to save file
    destination = Folder

    # download the file
    out_file = video.download(output_path=destination)

    # save the file
    base, ext = os.path.splitext(out_file)
    extension = '.mp3'
    suffix = ""
    i = 1
    PotentialFilePath = os.path.join(Folder, "Audio" + suffix + extension)
    while os.path.exists(PotentialFilePath):
        i += 1
        suffix = str(i)
        PotentialFilePath = os.path.join(Folder, "Audio" + suffix + extension)
    new_file = PotentialFilePath
    os.rename(out_file, new_file)

    # result of success
    print(yt.title + " has been successfully downloaded.")
    filepath = os.path.join(destination, "AUDIO" + suffix + extension)
    VideoName = yt.title
    return (filepath, VideoName)

def downloadHERALD(url, UserID):  # Yeah, we reuse a lot of code here, but I don't really feel like fixing the function right now.
    """Downloads the video at the passed url.  Returns a tuple containing the file path and video name."""
    yt = YouTube(str(url))
    video = yt.streams.filter(only_audio=True).first()

    Folder = "HeraldProfiles"
    FileBaseName = str(UserID)
    # Check whether the specified path exists or not
    isExist = os.path.exists(Folder)
    if not isExist:
        os.makedirs(Folder)

    # check for destination to save file
    destination = Folder

    # download the file
    out_file = video.download(output_path=destination)

    # save the file
    base, ext = os.path.splitext(out_file)
    extension = '.mp3'
    suffix = ""
    i = 1
    PotentialFilePath = os.path.join(Folder, FileBaseName + suffix + extension)
    while os.path.exists(PotentialFilePath):
        i += 1
        suffix = str(i)
        PotentialFilePath = os.path.join(Folder, FileBaseName + suffix + extension)

    new_file = PotentialFilePath
    os.rename(out_file, new_file)

    # result of success
    print(yt.title + " has been successfully downloaded.")
    filepath = os.path.join(destination, FileBaseName + suffix + extension)
    VideoName = yt.title
    return (filepath, VideoName)


if __name__ == "__main__":
    Link = str(input("Enter the URL of the video you want to download: \n>> "))
    try:
        download(Link)
    except Exception as e:
        print(e)
