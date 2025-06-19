#!/usr/bin/env bash
set -euo pipefail

REPO=https://github.com/youruser/lotto-cover.git   # <—- change to your repo
RG=coverRG
STOR=coverstore$RANDOM
REGIONS=(eastus eastus2 southcentralus westus3 northeurope westeurope \
         uksouth francecentral swedencentral australiacentral2 \
         southeastasia japaneast brazilsouth canadacentral centralindia)

echo "==> RG + storage"
az group create -n $RG -l eastus -o none
az storage account create -g $RG -n $STOR -l eastus --sku Standard_LRS -o none
KEY=$(az storage account keys list -g $RG -n $STOR --query '[0].value' -o tsv)
az storage container create --account-name $STOR --account-key $KEY -n results -o none
SAS=$(az storage account generate-sas --account-name $STOR \
      --permissions acdlrw --services bf --resource-types sco \
      --expiry "$(date -u -d '+7 days' '+%Y-%m-%dT%H:%MZ')" -o tsv)

cat > cloud-init.yml <<EOF
#cloud-config
package_update: true
packages: [git, build-essential, python3.11, python3.11-venv, wget]
runcmd:
  - |
    set -e
    cd /opt
    git clone $REPO repo
    python3.11 -m venv venv
    source venv/bin/activate
    pip install -r repo/requirements.txt --quiet
    SEED=\$(echo \$(hostname) | tr -dc '0-9')
    python repo/src/hg_greedy_seed.py --seed \$SEED
    python repo/src/cp_sat_rowgen.py
    python repo/src/scip_branch_price.py
    python repo/src/proof_fullcover.py
    wget -q https://aka.ms/downloadazcopy-v10-linux -O az.tgz
    tar xf az.tgz --strip-components=1
    ./azcopy copy phaseC.json "https://$STOR.blob.core.windows.net/results/\$(hostname)-phaseC.json?$SAS"
EOF

echo "==> start one 64-core Spot VM per region"
for R in "${REGIONS[@]}"; do
  echo " • $R"
  az vm create -g $RG -n cover-$R \
    --image "Canonical:0001-com-ubuntu-server-jammy:22_04-lts:latest" \
    --size Standard_F64s_v2 --priority Spot --max-price -1 \
    --admin-username azureuser \
    --ssh-key-values ~/.ssh/id_rsa.pub \
    --location $R --custom-data cloud-init.yml -o none &
done
wait
echo "+++ all create requests sent."
echo "Check blobs with:"
echo "az storage blob list -c results --account-name $STOR --account-key $KEY --query [].name"
