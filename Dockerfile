FROM mcr.microsoft.com/playwright/python:v1.40.0-jammy

# Install SSH
RUN apt-get update && apt-get install -y openssh-server

# Setup Users & Passwords (FORCE method)
RUN mkdir /var/run/sshd
RUN echo 'root:mysecretpassword123' | chpasswd

# Setup Config (Append directly to verify it sticks)
RUN echo "PermitRootLogin yes" >> /etc/ssh/sshd_config
RUN echo "PasswordAuthentication yes" >> /etc/ssh/sshd_config

# Setup App
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY scrape_wellfound_pro.py .

# Start
EXPOSE 22
CMD ["/usr/sbin/sshd", "-D"]
