# Gamitin ang Official Image (v1.49.0 para match sa requirements)
FROM mcr.microsoft.com/playwright/python:v1.49.0-jammy

# 1. Override location (Para magkita ang script at browser)
ENV PLAYWRIGHT_BROWSERS_PATH=/root/.cache/ms-playwright

# 2. Install SSH Server
RUN apt-get update && apt-get install -y openssh-server

# 3. Setup SSH User & Password
RUN mkdir /var/run/sshd
RUN echo 'root:mysecretpassword123' | chpasswd
RUN echo "PermitRootLogin yes" >> /etc/ssh/sshd_config
RUN echo "PasswordAuthentication yes" >> /etc/ssh/sshd_config

# 4. Setup App Folder
WORKDIR /app

# 5. Install Dependencies (requirements.txt)
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# 6. Force Install Browsers (Para sigurado)
RUN playwright install chromium
RUN playwright install-deps

# 7. COPY ALL SCRIPTS (Ito ang magic para makuha pati weremoto)
# Ang ibig sabihin ng dot-to-dot (. .) ay "Kopyahin lahat ng files dito papunta sa container"
COPY . .

# 8. Start SSH
EXPOSE 22
CMD ["/usr/sbin/sshd", "-D"]
