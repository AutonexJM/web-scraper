# CHEAT CODE: Gamitin ang Official Image (May Python + Chrome + Playwright na sa loob!)
FROM mcr.microsoft.com/playwright/python:v1.40.0-jammy

# 1. Install SSH Server lang (kasi meron na tayong Browsers)
RUN apt-get update && apt-get install -y openssh-server

# 2. Setup SSH Password
RUN mkdir /var/run/sshd
# TANDAAN: Ito ang password na gagamitin mo sa n8n
RUN echo 'root:mysecretpassword123' | chpasswd
RUN sed -i 's/#PermitRootLogin prohibit-password/PermitRootLogin yes/' /etc/ssh/sshd_config

# 3. Setup App Folder
WORKDIR /app

# 4. Install other Python Libraries (BeautifulSoup, etc.)
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# 5. Copy the Script
COPY scrape_wellfound_pro.py .

# 6. Start SSH
EXPOSE 22
CMD ["/usr/sbin/sshd", "-D"]
