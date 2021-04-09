#!/usr/bin/env bash

# Expect 2 args or "show-containers" or "show-images"
if [[ $# -ne 2 ]] && [[ $1 != "--show-containers" ]] && [[ $1 != "--show-images" ]] ; then
    echo "Image not set or not found"
    exit 1
fi

OPTION=$1
IMAGE=$2

# Download image
pull_image() {
    sudo podman pull ${IMAGE}
}

# Remove image
remove_image() {
    sudo podman image rm ${IMAGE}
}

# Show containers
show_containers() {
    sudo podman ps -a
}

# Show image
show_images() {
    sudo podman image ls
}


if [ "$OPTION" = "--pull" ]; then
    pull_image
    exit 0
fi

if [ "$OPTION" = "--remove" ]; then
    remove_image
    exit 0
fi

if [ "$OPTION" = "--show-containers" ]; then
    show_containers
    exit 0
fi

if [ "$OPTION" = "--show-images" ]; then
    show_images
    exit 0
fi
