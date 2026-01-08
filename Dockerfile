# Gamitin ang Official Image
FROM mcr.microsoft.com/playwright/python:v1.48.0-jammy

# 1. Install SSH Server
RUN apt-get update && apt-get install -y openssh-server

# 2. Setup SSH User & Password
RUN mkdir /var/run/sshd
RUN echo 'root:mysecretpassword123' | chpasswd
RUN echo "PermitRootLogin yes" >> /etc/ssh/sshd_config
RUN echo "PasswordAuthentication yes" >> /etc/ssh/sshd_config

# 3. Setup App Folder
WORKDIR /app

# 4. Install Python Libraries
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# --- THE FIX: MANUAL INSTALL BROWSER ---
# Ito ang mag-aayos ng "Executable doesn't exist"
# Pipilitin niyang i-download ang browser na tugma sa installed version
RUN playwright install chromium
RUN playwright install-deps
# ---------------------------------------

# 5. Copy the Script
COPY scrape_wellfound_pro.py .

# 6. Start SSH
EXPOSE 22
CMD ["/usr/sbin/sshd", "-D"]
