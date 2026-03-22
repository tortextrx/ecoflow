
import paramiko
from pathlib import Path
HOST = '10.20.167.5'
USER = 'root'
PASS = 'o1wrNtxq2?fA'
REMOTE_PATH = '/home/ecoflow/app/static/index.html'
LOCAL_PATH = 'app/static/index.html'
try:
    content = Path(LOCAL_PATH).read_text('utf-8')
    client = paramiko.SSHClient()
    client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    client.connect(HOST, username=USER, password=PASS)
    sftp = client.open_sftp()
    with sftp.file(REMOTE_PATH, 'w') as sf: sf.write(content)
    sftp.close(); client.close()
    print("Final Localization Deploy OK")
except Exception as e: print(f"Error: {e}")
