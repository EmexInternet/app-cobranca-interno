import os,paramiko
host='89.117.32.226'; user='root'; password=os.environ['SAASTV_VPS_PASSWORD']
cmd="grep -inE 'cobranca|app_python_automacao|crontab' /root/.bash_history | tail -80 || true"
ssh=paramiko.SSHClient(); ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy()); ssh.connect(host,username=user,password=password,timeout=20)
_,o,e=ssh.exec_command(cmd,timeout=60)
print(o.read().decode()); print(e.read().decode()); ssh.close()
