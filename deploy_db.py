import paramiko
import os

HOST, USER, PASS = "10.20.167.5", "root", "o1wrNtxq2?fA"
REMOTE_DIR = "/home/ecoflow"

FILES = [
    r"c:\Users\Javier\Desktop\PROYECTO WHATSAPP\app\models\db\conversation.py",
    r"c:\Users\Javier\Desktop\PROYECTO WHATSAPP\app\models\schemas\identity.py",
    r"c:\Users\Javier\Desktop\PROYECTO WHATSAPP\app\repositories\conversation_repo.py",
    r"c:\Users\Javier\Desktop\PROYECTO WHATSAPP\app\services\chat_service.py",
    r"c:\Users\Javier\Desktop\PROYECTO WHATSAPP\app\main.py",
]

def deploy():
    client = paramiko.SSHClient()
    client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    print(f"Connecting to {HOST}...")
    client.connect(HOST, username=USER, password=PASS)
    sftp = client.open_sftp()
    
    for f in FILES:
        remote_path = f.replace(r"c:\Users\Javier\Desktop\PROYECTO WHATSAPP", REMOTE_DIR).replace("\\", "/")
        print(f"Uploading {f} -> {remote_path}")
        try:
            sftp.put(f, remote_path)
        except IOError:
            sftp.mkdir(os.path.dirname(remote_path))
            sftp.put(f, remote_path)
    
    # Run the DB migration
    print("Running DB migration on remote...")
    cmd_db = 'sudo -u postgres psql -d ecoflow_db -c "ALTER TABLE conversations ADD COLUMN IF NOT EXISTS session_data JSONB DEFAULT \'{}\';"'
    stdin, stdout, stderr = client.exec_command(cmd_db)
    print(stdout.read().decode())
    err = stderr.read().decode()
    if err:
        print("MIGRATION ERROR:", err)
    else:
        print("Migration successful")
    
    sftp.close()
    client.close()

if __name__ == "__main__":
    deploy()
