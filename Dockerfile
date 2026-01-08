# 1. Base Image: Microsoft Playwright (v1.49.0)
# Match na match ito sa requirements.txt mo.
# Meron na itong Python at Chrome. HINDI na magda-download.
FROM mcr.microsoft.com/playwright/python:v1.49.0-jammy

# 2. Install SSH Server (Ito lang ang kulang)
RUN apt-get update && apt-get install -y openssh-server

# 3. Setup SSH Access
RUN mkdir /var/run/sshd
RUN echo 'root:mysecretpassword123' | chpasswd
RUN echo "PermitRootLogin yes" >> /etc/ssh/sshd_config
RUN echo "PasswordAuthentication yes" >> /etc/ssh/sshd_config

# 4. App Setup
WORKDIR /app

# 5. Install Dependencies (Mabilis na lang to kasi naka-lock version)
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# 6. Copy Code & Start
COPY scrape_wellfound_pro.py .
EXPOSE 22
CMD ["/usr/sbin/sshd", "-D"]
