
import paramiko
import os

HOST = '10.20.167.5'
USER = 'root'
PASS = 'o1wrNtxq2?fA'
BASE_PATH = '/home/ecoflow/app/static/'
LOCAL_BASE = 'app/static/'

files = ['index.html', 'avatar.png']

try:
    client = paramiko.SSHClient()
    client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    client.connect(HOST, username=USER, password=PASS)
    sftp = client.open_sftp()

    for f in files:
        remote = os.path.join(BASE_PATH, f).replace('\\', '/')
        local = os.path.join(LOCAL_BASE, f)
        sftp.put(local, remote)
        print(f"Uploaded: {f}")

    sftp.close()
    client.close()
    print("Avatar Deploy OK")

except Exception as e:
    print(f"Error: {e}")
