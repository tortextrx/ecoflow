import argparse
import paramiko
from pathlib import Path


def put_file(local_path: str, remote_path: str) -> None:
    host = "10.20.167.5"
    user = "root"
    password = "o1wrNtxq2?fA"

    lp = Path(local_path)
    if not lp.exists():
        raise FileNotFoundError(f"Local file not found: {local_path}")

    client = paramiko.SSHClient()
    client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    client.connect(hostname=host, username=user, password=password, timeout=30)
    try:
        sftp = client.open_sftp()
        try:
            sftp.put(str(lp), remote_path)
        finally:
            sftp.close()
    finally:
        client.close()


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("local_path")
    parser.add_argument("remote_path")
    args = parser.parse_args()
    put_file(args.local_path, args.remote_path)
    print("OK")
