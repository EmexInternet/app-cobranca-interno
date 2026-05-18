import os, paramiko
host='89.117.32.226'; user='root'; password=os.environ['SAASTV_VPS_PASSWORD']
cmd="pwd; echo '---'; ls -la; echo '---CRON---'; crontab -l || true; echo '---DIRS---'; find / -maxdepth 3 -type d \\( -iname '*cobranca*' -o -iname 'logs' \\) 2>/dev/null | head -80"
ssh=paramiko.SSHClient(); ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy()); ssh.connect(host, username=user, password=password, timeout=20)
stdin, stdout, stderr = ssh.exec_command(cmd, timeout=60)
print(stdout.read().decode('utf-8','replace'))
err=stderr.read().decode('utf-8','replace')
if err: print('STDERR:',err)
ssh.close()
