FROM python:3.11

# Install Chrome dependencies
RUN apt-get update && apt-get install -y \
    wget \
    gnupg \
    unzip \
    xvfb \
    libxi6 \
    libgconf-2-4 \
    libnss3 \
    libfontconfig1 \
    libxcb1 \
    xauth \
    dbus-x11 \
    libxrender1 \
    libxtst6 \
    libxss1 \
    libgtk-3-0 \
    libasound2

# Install Chrome
RUN wget -q -O - https://dl-ssl.google.com/linux/linux_signing_key.pub | apt-key add - \
    && echo "deb http://dl.google.com/linux/chrome/deb/ stable main" >> /etc/apt/sources.list.d/google.list \
    && apt-get update \
    && apt-get install -y google-chrome-stable

# Set up virtual display
ENV DISPLAY=:99
RUN mkdir -p /tmp/.X11-unix && chmod 1777 /tmp/.X11-unix
RUN mkdir -p /var/run/dbus && chown messagebus:messagebus /var/run/dbus

# Install Python dependencies
COPY requirements.txt .
RUN pip install -r requirements.txt

WORKDIR /app
COPY . /app

# Start Xvfb and run the script
CMD Xvfb :99 -screen 0 1920x1080x24 -ac +extension GLX +render -noreset & \
    python membean.py
