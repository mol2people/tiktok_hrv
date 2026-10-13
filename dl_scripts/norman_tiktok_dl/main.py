import pandas as pd
import yt_dlp
import paramiko
import os
import subprocess

from datetime import datetime
from pathlib import Path


# link file
LINK_TABLE_FILE_PATH = "links.csv"

# SSH creds
REMOTE_SSH_CONFIG = "Config"
REMOT_BASE_PATH = "/"


def set_up_directories():
    today_str = datetime.now().strftime("%Y_%m_%d")
    folder_name = f"videos_{today_str}"
    local_path = Path.cwd() / folder_name

    # create local dir if not exists
    if not local_path.exists():
        local_path.mkdir(parents=True)


    # create remote dir
    remote_full_path = f"{REMOT_BASE_PATH}/{folder_name}"
    #ssh_cmd = ["ssh", f"{REMOTE_SSH_CONFIG}", f"mkdir -p {remote_full_path}"]
    #try:
    #   subprocess.run(ssh_cmd, check=True)
    #except subprocess.CalledProcessError as e:
    #   print(f"Error with subprocess call: {e}")

    return folder_name


def download_tiktok(url, folder_name):
    print(f"start download for url: {url}  ", end="")
    
    # yt-dlp options
    ydl_opts = {
        'outtmpl': folder_name + '/%(id)s.%(ext)s', 
        'format': 'bestvideo[ext=mp4]+bestaudio[ext=m4a]/best[ext=mp4]/best',
        'quiet': True
    }

    # download part
    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=True)
            filename = ydl.prepare_filename(info)
            print("- Success")
            return filename
    except Exception as e:
        print(f"- Error, download failed!")
        return None



def upload_to_server(local_filepath):
    print(f"connect to {host}...")
    
    # flag if successful
    success = False

    # SSH Client
    ssh = paramiko.SSHClient()
    ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy()) 
    
    try:
        ssh.connect(
            hostname=HOST, 
            port=PORT, 
            username=USERNAME, 
            password=PASSWORD, 
            key_filename=KEY_FILEPATH
        )
        
        # SFTP connection
        sftp = ssh.open_sftp()
        
        # remote path
        filename = os.path.basename(local_filepath)
        remote_filepath = os.path.join(REMOTE_DIR, filename).replace('\\', '/')
        
        print(f"Upload '{filename}' to HPC '{remote_filepath}' ", end="")
        sftp.put(local_filepath, remote_filepath)
        print("- Success!")
        
        sftp.close()
        success = True
    except Exception as e:
        print("- Error, upload failed!")
    finally:
        ssh.close()
    
    return success

def main():
    df = pd.read_csv(LINK_TABLE_FILE_PATH, low_memory=False)
    for row in df.iterrows():
        row = row[1]
        url, done = row["links"], row["done"]
        if done:
            continue
        folder_name = set_up_directories()
        local_filepath = download_tiktok(url, folder_name)
        if not local_filepath:
            print(f"Error while download, url: {url}")
            continue
        # success_flag = upload_to_server(local_filepath)
        success_flag = True
        if not success_flag:
            print(f"Error while upload, url: {url}")
            continue
        print(f"Success! url: {url}")
        df.loc[df['links'] == url, 'done'] = True
        df.to_csv(LINK_TABLE_FILE_PATH, lineterminator="\r\n", index=False)
    

if __name__ == '__main__':
    main()
