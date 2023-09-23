"""Video Downloading module made to support Uni_Bot.py.

This module downloads a video from YouTube in MP3 format and saves it in the appropriate folder.
The specific location the video is saved in is dependent on the function that is called.

Typical usage example:

my_video_url = "https://www.youtube.com/watch?v=dQw4w9WgXcQ"

audio1 = download(my_video_url)

herald_theme = herald_download(my_video_url, 12345678)
"""

from pytube import YouTube
import os
import logging

logger = logging.getLogger('download')


async def download(url):
    """Downloads the video at the passed url.

    Async.io compatible function that downloads the audio channel of the YouTube video at the passed
    URL.  The file is stored at a location determined by the constant FOLDER.  By default, the file
    is simply named "AudioX.mp3" in order to prevent long and/or repeating file names.

    Args:
        url: String containing the URL of the YouTube video that is to be downloaded.

    Returns:
        A tuple containing the filepath to the downloaded audio track as well as the video name.
        For example:

        ('/home/admin/video_folder/audio1.MP3', 'Video_Name')
    """
    DIR_NAME = "MusicQueue"

    yt = YouTube(str(url))
    logger.debug("Beginning Stream Search...")
    video = yt.streams.filter(only_audio=True).first()
    logger.debug("Found Stream")
    # Check whether the specified path exists or not
    if not os.path.exists(DIR_NAME):
        os.makedirs(DIR_NAME)

    # check for destination to save file
    destination = DIR_NAME

    # download the file
    logger.debug("Beginning Download")
    out_file = video.download(output_path=destination)
    logger.debug("Download Complete")

    # save the file
    base, ext = os.path.splitext(out_file)
    extension = '.mp3'
    suffix = ""
    i = 1
    potential_filepath = os.path.join(DIR_NAME, "Audio" + suffix + extension)
    while os.path.exists(potential_filepath):  # Agree upon a unique filename
        i += 1
        suffix = str(i)
        potential_filepath = os.path.join(DIR_NAME, "Audio" + suffix + extension)
    new_file = potential_filepath
    os.rename(out_file, new_file)

    # result of success
    logger.info(yt.title + " has been successfully downloaded.")
    filepath = os.path.join(destination, "Audio" + suffix + extension)
    vid_name = yt.title
    return (filepath, vid_name)


def download_herald(url, user_id):
    """Downloads the video at the passed url and assigns it as the HeraldTheme for the UserID.

    Downloads the video at the passed URL in MP3 format to be used as the herald theme for the user
    with discord UserID, user_id. The file is stored at a location determined by constant FOLDER.
    By default, the file is named "<user_id>.mp3" in order to maintain consistent, non-repeating
    file names.

    Args:
        url: String containing the URL of the YouTube video that is to be downloaded.
        user_id: Integer containing the user_id of the discord user.

    Returns:
        A tuple containing the filepath to the downloaded audio track as well as the video name.
        For example:

        ('/home/admin/video_folder/<user_id>.MP3', 'Video_Name')
    """
    DIR_NAME = "HeraldProfiles"
    FILE_BASE_NAME = str(user_id)

    yt = YouTube(str(url))
    video = yt.streams.filter(only_audio=True).first()

    # Check whether the specified path exists or not
    isExist = os.path.exists(DIR_NAME)
    if not isExist:
        os.makedirs(DIR_NAME)
    destination = DIR_NAME

    # download the file
    out_file = video.download(output_path=destination)

    # save the file
    base, ext = os.path.splitext(out_file)
    extension = '.mp3'
    suffix = ""
    i = 1
    potential_filepath = os.path.join(DIR_NAME, FILE_BASE_NAME + suffix + extension)
    while os.path.exists(potential_filepath):
        i += 1
        suffix = str(i)
        potential_filepath = os.path.join(DIR_NAME, FILE_BASE_NAME + suffix + extension)

    new_file = potential_filepath
    os.rename(out_file, new_file)

    # result of success
    logger.info(yt.title + " has been successfully downloaded.")
    filepath = os.path.join(destination, FILE_BASE_NAME + suffix + extension)
    vid_name = yt.title
    return (filepath, vid_name)


if __name__ == "__main__":
    logging.basicConfig('video_download.log', level=logging.DEBUG)
    url = str(input("Enter the URL of the video you want to download: \n>> "))
    try:
        download(url)
    except Exception as e:
        print(e)
