---
lastproofread: '2026-02-02'
---

(proxmox)=

# Running on Proxmox

Proxmox is an open-source platform for virtualization. Visit
<https://vyos.io> to download a `.qcow2` image that you can import into
Proxmox.

## Deploy VyOS from CLI with qcow2 image

1. Copy the `.qcow2` image to a temporary directory on the Proxmox server.
2. The commands assume virtual machine ID 200 is unused and you want
   the disk stored in a storage pool named `local-lvm`.

```none
$ qm create 200 --name vyos2 --memory 2048 --net0 virtio,bridge=vmbr0
$ qm importdisk 200 /path/to/image/vyos-1.2.8-proxmox-2G.qcow2 local-lvm
$ qm set 200 --virtio0 local-lvm:vm-200-disk-0
$ qm set 200 --boot order=virtio0
```

3. You can optionally attach a CDROM with an ISO as a cloud-init data
   source. The command assumes the ISO is uploaded to the `local`
   storage pool as `seed.iso`.

```none
$ qm set 200 --ide2 media=cdrom,file=local:iso/seed.iso
```

4. Start the virtual machine using the Proxmox GUI or run `qm start 200`.

## Deploy VyOS from CLI with rolling release ISO

1. Download the rolling release ISO from
   <https://vyos.net/get/nightly-builds/>. Non-subscribers can use the
   LTS release by building from source. For instructions, see the
   {ref}`build` section. The VyOS source code repository
   is available at <https://github.com/vyos/vyos-build>.
2. Prepare the VM for ISO installation. The commands assume your ISO is
   in storage pool 'local', you want VM ID '200', and you want to create
   a new 15GB disk on storage pool 'local-lvm'.

```none
qm create 200 --name vyos --memory 2048 --net0 virtio,bridge=vmbr0 --ide2 media=cdrom,file=local:iso/live-image-amd64.hybrid.iso --virtio0 local-lvm:15
```

3. Start the VM using `qm start 200` or the start button in the
   Proxmox GUI.
4. Open the virtual console for your VM using the Proxmox web GUI.
   Login username and password are both `vyos`.
5. Once booted into the live system, type `install image` and follow
   the prompts to install VyOS to the virtual drive.
6. After installation completes, remove the installation ISO using the
   GUI or run `qm set 200 --ide2 none`.
7. Reboot the virtual machine using the GUI or run `qm reboot 200`.

For more information about downloading and installing Proxmox, visit
<https://www.proxmox.com/en/>.
