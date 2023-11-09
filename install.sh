#!/usr/bin/bash

###############################################################################
# This scripts is for deploying Sourcegraph in a VM environment
# Customizable Variables
###############################################################################
# INSTANCE_VERSION=4.2.0 # Sourcegraph Version
# INSTANCE_SIZE=XS  # Sourcegraph Size e.g. XS / S / M / L / XL
# VOLUME_DEVICE_NAME=/dev/sdb # Persistent Data Disk

###############################################################################
# IMPORTANT: FOR INTERNAL USE ONLY
# Internal Variables
###############################################################################

#~~~~~~~~~~~~~~~~~~~~ NO CHANGES REQUIRED BELOW THIS LINE ~~~~~~~~~~~~~~~~~~~~#

###############################################################################
# Parse arguments
###############################################################################
while getopts "v:s:d:" opt; do
    case $opt in
        v)
            INSTANCE_VERSION=$OPTARG
            ;;
        s)
            INSTANCE_SIZE=$OPTARG
            ;;
        d)
            VOLUME_DEVICE_NAME=$OPTARG
            ;;
        \?)
            echo "Invalid option: -$OPTARG" >&2
            exit 1
            ;;
    esac
done

if [ -z "$VOLUME_DEVICE_NAME" ]; then
    echo "❌ Error: the '-d <data disk device>' option is required" >&2
    exit 1
fi

###############################################################################
# Default Variables
###############################################################################
# Make sure the v is removed from the version number
SOURCEGRAPH_VERSION=${INSTANCE_VERSION#v}
SOURCEGRAPH_SIZE=$INSTANCE_SIZE
SOURCEGRAPH_DEPLOY_REPO_URL='https://github.com/sourcegraph/deploy'
DEPLOY_PATH="$HOME/deploy/install"
KUBECONFIG='/etc/rancher/k3s/k3s.yaml'
INSTANCE_ID=''
INSTANCE_USERNAME=$(whoami)

###############################################################################
# Prepare the system user
# If running as root, exit. The remainder of this script
# will always use `sudo` to indicate where root is required, so that it is clear
# what does and does not require root in our installation process.
###############################################################################
if [ $UID -eq 0 ]; then
    echo "❌ Error: run the script as non-root user with 'sudo' priveleges"
    exit 1
fi
# Set defaults
SOURCEGRAPH_VERSION=${SOURCEGRAPH_VERSION:-''} # Default to empty
SOURCEGRAPH_SIZE=${SOURCEGRAPH_SIZE:-'XS'}  # Default to XS

# Check the disk exists
if [ ! -b "${VOLUME_DEVICE_NAME}" ]; then
    if [ -f "${VOLUME_DEVICE_NAME}" ] || [ -d "${VOLUME_DEVICE_NAME}" ]; then
        echo "❌ Error: Data Disk '${VOLUME_DEVICE_NAME}' not a block device"
        exit 1
    fi
    echo "❌ Error: Data Disk not found: '${VOLUME_DEVICE_NAME}'"
    exit 1
fi


###############################################################################
# OS Detection
# Parses /etc/os-release file
# Parse `distro` from `ID="distro"`
###############################################################################
ID=$(grep ^ID= /etc/os-release | sed -E 's/ID="?([0-9a-z._-]*)"?/\1/')
case $ID in
    rhel | amzn | fedora)
        INSTANCE_ID="fedora"
        ;;
    debian | ubuntu)
        INSTANCE_ID="debian"
        ;;
    *)
        echo "❌ Error: unsupported distro"
        exit 1
        ;;
esac

###############################################################################
# System Prep
# Install required packages
# Enable/Disable any pre-installed services
###############################################################################
cd || exit
if [ "$INSTANCE_ID" = "fedora" ]; then
    sudo yum update -y
    sudo yum install git container-selinux -y
elif [ "$INSTANCE_ID" = "debian" ]; then
    sudo apt-get update -y
    sudo apt-get install -y git 
fi

# firewalld interferes with k3s networking
if  systemctl is-active firewalld.service; then
    sudo systemctl disable firewalld.service
    sudo systemctl stop firewalld.service
fi

# k3s will not run if nm-cloud-setup.service is active
if systemctl is-active nm-cloud-setup.service || systemctl is-enabled nm-cloud-setup.service; then
    sudo systemctl disable nm-cloud-setup.service
    sudo systemctl disable nm-cloud-setup.timer
    sudo systemctl stop nm-cloud-setup.service
fi

# Clone the deployment repository
[ ! -d "$HOME/deploy" ] && git clone $SOURCEGRAPH_DEPLOY_REPO_URL
cp "$HOME/deploy/install/override.$SOURCEGRAPH_SIZE.yaml" "$HOME/deploy/install/override.yaml"

###############################################################################
# Kernel parameters required by Sourcegraph
###############################################################################
# These must be set in order for Zoekt (Sourcegraph's search indexing backend)
# to perform at scale without running into limitations.
sudo sh -c "echo 'fs.inotify.max_user_watches=128000' >> /etc/sysctl.conf"
sudo sh -c "echo 'vm.max_map_count=300000' >> /etc/sysctl.conf"
sudo sysctl --system # Reload configuration (no restart required.)
sudo sh -c "echo '* soft nproc 8192' >> /etc/security/limits.conf"
sudo sh -c "echo '* hard nproc 16384' >> /etc/security/limits.conf"
sudo sh -c "echo '* soft nofile 262144' >> /etc/security/limits.conf"
sudo sh -c "echo '* hard nofile 262144' >> /etc/security/limits.conf"

###############################################################################
# Configure data volumes for the Sourcegraph k3s instance
###############################################################################
# If Data Disk is not mounted to /mnt/data
if ! df | grep "${VOLUME_DEVICE_NAME}" | grep -q "/mnt/data"; then
    # Create mounting directories for storing data from the Sourcegraph cluster
    sudo mkdir -p /mnt/data
    # Format (if necessary) and mount the data volume
    device_fs=$(sudo lsblk "$VOLUME_DEVICE_NAME" --noheadings --output fsType)
    if [ -z "$device_fs" ]; then
        # If `xfs_admin` available
        if command -v xfs_admin &> /dev/null; then
            sudo mkfs -t xfs "$VOLUME_DEVICE_NAME"
            sudo xfs_admin -L /mnt/data "$VOLUME_DEVICE_NAME" # Add label to volume device
            mount_opts="LABEL=/mnt/data  /mnt/data  xfs  discard,defaults,nofail  0  2"
        else
            sudo mkfs.ext4 -m 0 -E lazy_itable_init=0,lazy_journal_init=0,discard "$VOLUME_DEVICE_NAME"
            sudo e2label "$VOLUME_DEVICE_NAME" /mnt/data # Add label to volume device
            mount_opts="LABEL=/mnt/data  /mnt/data  ext4  discard,defaults,nofail  0  2"
        fi
        sudo mount "$VOLUME_DEVICE_NAME" /mnt/data
        # Mount data disk on reboots by linking disk label to data root path
        sudo echo "$mount_opts" | sudo tee -a /etc/fstab
    else
        # Add fstab if missing but disk is formatted
        if ! grep "LABEL=/mnt/data" /etc/fstab; then
            sudo echo "LABEL=/mnt/data  /mnt/data  $device_fs  discard,defaults,nofail  0  2" | sudo tee -a /etc/fstab
        fi
        sudo mount "$VOLUME_DEVICE_NAME" /mnt/data
    fi
    sudo mount -a

    # Put ephemeral kubelet/pod storage in our data disk (since it is the only large disk we have.)
    # Symlink `/var/lib/kubelet` to `/mnt/data/kubelet`
    sudo mkdir -p /mnt/data/kubelet
    sudo ln -s /mnt/data/kubelet /var/lib/kubelet

    # Put persistent volume pod storage in our data disk, and k3s's embedded database there too (it
    # must be kept around in order for k3s to keep PVs attached to the right folder on disk if a node
    # is lost (i.e. during an upgrade of Sourcegraph), see https://github.com/rancher/local-path-provisioner/issues/26
    sudo mkdir -p /mnt/data/db
    sudo mkdir -p /var/lib/rancher/k3s/server
    sudo ln -s /mnt/data/db /var/lib/rancher/k3s/server/db
    sudo mkdir -p /mnt/data/storage
    sudo mkdir -p /var/lib/rancher/k3s
    sudo ln -s /mnt/data/storage /var/lib/rancher/k3s/storage
fi

###############################################################################
# Install k3s (Kubernetes single-machine deployment)
###############################################################################
declare -a additional_args=()

# SeLinux support
if command -v getenforce && getenforce | grep 'Enforcing|Permissive'; then
    additional_args+=("--selinux")
fi
curl -sfL https://get.k3s.io | INSTALL_K3S_VERSION=v1.26.2+k3s1 K3S_TOKEN=none sh -s - \
        --node-name sourcegraph-0 \
        --write-kubeconfig /etc/rancher/k3s/k3s.yaml \
        --write-kubeconfig-mode 644 \
        --cluster-cidr 10.10.0.0/16 \
        --kubelet-arg containerd=/run/k3s/containerd/containerd.sock \
        --etcd-expose-metrics true "${additional_args[@]}"
# Confirm k3s and kubectl are up and running
sleep 10 && k3s kubectl get node
# Correct permissions of k3s config file
sudo chown "$INSTANCE_USERNAME" /etc/rancher/k3s/k3s.yaml
sudo chmod go-r /etc/rancher/k3s/k3s.yaml
cp /etc/rancher/k3s/k3s.yaml "$HOME/.kube/config"
# Add standard bash aliases
echo 'export KUBECONFIG=/etc/rancher/k3s/k3s.yaml' | tee -a "$HOME/.bash_profile"
echo "alias k='kubectl --kubeconfig /etc/rancher/k3s/k3s.yaml'" | tee -a "$HOME/.bash_profile"
echo "alias h='helm --kubeconfig /etc/rancher/k3s/k3s.yaml'" | tee -a "$HOME/.bash_profile"

###############################################################################
# Deploy Sourcegraph with Helm
###############################################################################
cd "$DEPLOY_PATH" || {
    echo "❌ Error: could not change directory into '$DEPLOY_PATH'"
    exit 1
}
# Install Helm
if ! command -v helm &> /dev/null; then
    curl -sSL https://raw.githubusercontent.com/helm/helm/master/scripts/get-helm-3 | bash
    helm --kubeconfig $KUBECONFIG repo add sourcegraph https://helm.sourcegraph.com/release
else
    # Helm already installed - update chart repos
    helm repo update &> /dev/null
fi

# Get latest Sourcegraph version if none supplied
if [ -z "$SOURCEGRAPH_VERSION" ]; then
    SOURCEGRAPH_VERSION=$(helm inspect chart sourcegraph/sourcegraph | grep version: | sed -E 's/version: (.*)/\1/')
fi

if ! helm show chart --version "$SOURCEGRAPH_VERSION" sourcegraph/sourcegraph; then
    echo "❌ Error: could not find Sourcegraph Version '$SOURCEGRAPH_VERSION'"
    exit 1
fi
# Pull the Sourcegraph chart
helm --kubeconfig $KUBECONFIG pull --version "$SOURCEGRAPH_VERSION" sourcegraph/sourcegraph
mv "$HOME/deploy/install/sourcegraph-$SOURCEGRAPH_VERSION.tgz" "$HOME/deploy/install/sourcegraph-charts.tgz"
# Store Sourcegraph executor k8s charts
helm --kubeconfig $KUBECONFIG pull --version "$SOURCEGRAPH_VERSION" sourcegraph/sourcegraph-executor-k8s
mv "$HOME/deploy/install/sourcegraph-executor-k8s-$SOURCEGRAPH_VERSION.tgz" "$HOME/deploy/install/sourcegraph-executor-k8s-charts.tgz"
# Create override configMap for prometheus before startup Sourcegraph
k3s kubectl apply -f "$HOME/deploy/install/prometheus-override.ConfigMap.yaml"
# Create ingress
k3s kubectl create -f "$HOME/deploy/install/ingress.yaml"
# Deploy Sourcegraph
helm --kubeconfig $KUBECONFIG upgrade -i -f ./override.yaml --version "$SOURCEGRAPH_VERSION" sourcegraph "$HOME/deploy/install/sourcegraph-charts.tgz"
sleep 5
helm --kubeconfig $KUBECONFIG upgrade -i -f ./override.yaml --version "$SOURCEGRAPH_VERSION" executor "$HOME/deploy/install/sourcegraph-executor-k8s-charts.tgz"

# Generate files to save instance info in volumes for upgrade purpose
# First, pin the root image with the version number
sudo echo "$SOURCEGRAPH_VERSION" | sudo tee "$HOME/.sourcegraph-version"
sudo echo "${SOURCEGRAPH_VERSION}" | sudo tee /mnt/data/.sourcegraph-version

# Deploy Reboot
echo "@reboot sleep 10 && bash $HOME/deploy/install/scripts/k3s/reboot.sh" | sudo crontab -u "$INSTANCE_USERNAME" -
