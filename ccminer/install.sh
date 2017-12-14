sudo -n
apt-get -y update
dpkg-reconfigure debconf -f noninteractive
apt-get -y install software-properties-common git 
add-apt-repository -y ppa:graphics-drivers/ppa
apt-get -y update
NVIDIA_DRIVER_VERSION="384"
apt-get install -y nvidia-$NVIDIA_DRIVER_VERSION-dev nvidia-$NVIDIA_DRIVER_VERSION nvidia-cuda-toolkit
apt-get install -y libcurl4-openssl-dev libssl-dev libjansson-dev automake autotools-dev build-essential
apt-get install -y gcc-5 g++-5
update-alternatives --install /usr/bin/gcc gcc /usr/bin/gcc-5 1
git clone https://github.com/tpruvot/ccminer.git
cd ccminer/
./build.sh
./ccminer --version
