#!/bin/sh

USER=`whoami`
MINING_DIR="$HOME/_mining/"
NVIDIA_DRIVER_VERSION="384"

# run this script: cd nvidia_rig; chmod +x ./nvidia_rig_install.sh; ./nvidia_rig_install.sh

# zec miner variables
ZEC_MINER_FILE_ID="0B9EPp8NdigFiV1AwZW1lY2tEcjA"
ZEC_MINING_DIR="$MINING_DIR/zec/"
ZEC_MINER_URL="https://drive.google.com/uc?export=download&id=$ZEC_MINER_FILE_ID"
ZEC_MINER_FILE='Zec_Miner_0_3_4b.tar.gz'


# add user to groups video, sudo
sudo gpasswd -a $USER video
sudo gpasswd -a $USER sudo

# update and upgrade system
sudo apt -y update; sudo apt -y upgrade

# add nvidia drivers repo
sudo add-apt-repository -y ppa:graphics-drivers/ppa
sudo apt-get -y update

# install all required packages
sudo apt install -y python3 tmux openssh-server autossh mc htop atop dstat nvidia-$NVIDIA_DRIVER_VERSION-dev nvidia-$NVIDIA_DRIVER_VERSION

# configure Xorg server
sudo nvidia-xconfig -a --cool-bits=31 --allow-empty-initial-configuration --enable-all-gpus --registry-dwords='PerfLevelSrc=0x2222' --connected-monitor='DFP-0'

# configure sudo
echo '%video    ALL=NOPASSWD: ALL' | sudo tee /etc/sudoers.d/nvidia

# add autorun commands, they start after graphic server
echo "tmux new -s nvset -d 'python3 $HOME/nvset.py -c $HOME/nv.ini -D' # autostart nvidia overclock tool in background. Command for attach: tmux attach -t nvset\ntmux new -s zec_miner -d 'cd $HOME/_mining/zec/0.3.4b; ./miner --config miner.cfg'\nsudo nvidia-xconfig -a --cool-bits=31 --allow-empty-initial-configuration --enable-all-gpus --registry-dwords='PerfLevelSrc=0x2222' --connected-monitor='DFP-0' & # reconfigure graphic server\n" | tee $HOME/.xprofile

# add autologon for current user
printf "[SeatDefaults]\nautologin-user=$USER\nautologin-user-timeout=0\nuser-session=ubuntu\ngreeter-session=unity-greeter" | sudo tee /etc/lightdm/lightdm.conf.d/01-autologin.conf

# copy nvidia overclock tool to home directory of current user
cp -v ./nvset.py $HOME; cp -v ./nv.ini $HOME

# download zec miner
mkdir $MINING_DIR; cd $MINING_DIR; wget $ZEC_MINER_URL -O $ZEC_MINER_FILE
mkdir -p $ZEC_MINING_DIR; tar xzvf $ZEC_MINER_FILE -C $ZEC_MINING_DIR

# download and install teamviewer, this operation is optional and can be commented
wget -c https://download.teamviewer.com/download/teamviewer_i386.deb; sudo dpkg -i teamviewer_i386.deb; sudo apt install -y -f

echo 'System reboot in 10 seconds. Please enter your password if needed'
sudo reboot
