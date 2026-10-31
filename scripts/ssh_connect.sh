#!/usr/bin/env bash

# Définition des variables
RASPBERRY_PI_USER="msorel"
RASPBERRY_PI_HOST="rasp-berry-king.local"
RASPBERRY_PI_IP_FALLBACK="172.20.10.2"

# Lancement de XQuartz...
pgrep -x X11.bin > /dev/null 2>&1
if [ $? -ne 0 ]; then
    echo "X11 n'est pas lancé. Lancement de XQuartz..."
    open -a XQuartz
    sleep 2
else
    echo "X11 est déjà lancé."
fi

# Autorisation des connexions SSH avec X11 forwarding
echo "2. Autorisation des connexions SSH avec X11 forwarding..."
xhost +localhost

# Cherche le Raspberry Pi sur le réseau local
echo "3. Test de résolution du nom du Pi ($RASPBERRY_PI_HOST)..."
ping -c 1 -W 1000 "$RASPBERRY_PI_HOST" >/dev/null 2>&1
if [ $? -ne 0 ]; then
    echo "Échec de la résolution du nom. Test de l'adresse IP de secours ($RASPBERRY_PI_IP_FALLBACK)..."
    ping -c 1 -W 1000 "$RASPBERRY_PI_IP_FALLBACK" > /dev/null 2>&1
    if [ $? -ne 0 ]; then
        echo "Échec de l'adresse IP de secours. Impossible de joindre le Raspberry Pi."
        exit 1
    else
        echo "Adresse IP de secours OK."
        RASPBERRY_PI_HOST=$RASPBERRY_PI_IP_FALLBACK
    fi
fi

# Connexion SSH au Raspberry Pi
echo "4. Connexion SSH au Raspberry Pi..."
ssh -Y $RASPBERRY_PI_USER@$RASPBERRY_PI_HOST

echo "Session terminée."