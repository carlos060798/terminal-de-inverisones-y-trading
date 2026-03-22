# Guia de Despliegue — Quantum Retail Terminal

Esta guia cubre 4 opciones de despliegue, desde la mas facil (Streamlit Cloud) hasta la mas potente (VPS dedicado).

## Requisitos Previos

- Cuenta de GitHub con el repositorio clonado/forkeado
- API keys (al menos una para funcionalidad AI):
  - **FRED_API_KEY** — datos macroeconomicos (gratis en https://fred.stlouisfed.org/docs/api/api_key.html)
  - **GROQ_API_KEY** — analisis AI con Groq (gratis en https://console.groq.com)
  - **GEMINI_API_KEY** — analisis AI con Google Gemini (gratis en https://aistudio.google.com/apikey)
  - **OPENROUTER_API_KEY** — fallback AI via OpenRouter (https://openrouter.ai/keys)

---

## Opcion 1: Streamlit Cloud (GRATIS, mas facil)

La forma mas rapida de desplegar. No requiere configuracion de servidor.

### Paso 1: Preparar el repositorio

Asegurate de que tu repositorio en GitHub contiene:
- `app.py` (punto de entrada)
- `requirements.txt` (dependencias)
- `.streamlit/config.toml` (configuracion del tema)

### Paso 2: Crear cuenta en Streamlit Cloud

1. Ve a https://share.streamlit.io
2. Inicia sesion con tu cuenta de GitHub
3. Autoriza el acceso a tus repositorios

### Paso 3: Desplegar la app

1. Haz clic en **"New app"**
2. Selecciona tu repositorio: `carlos060798/terminal-de-inverisones-y-trading`
3. Branch: `main`
4. Main file path: `app.py`
5. Haz clic en **"Deploy"**

### Paso 4: Configurar Secrets

1. En el panel de la app desplegada, ve a **Settings** (icono de engranaje)
2. Selecciona **Secrets**
3. Pega tus API keys en formato TOML:

```toml
FRED_API_KEY = "tu-key-aqui"
GROQ_API_KEY = "tu-key-aqui"
OPENROUTER_API_KEY = "tu-key-aqui"
GEMINI_API_KEY = "tu-key-aqui"
```

4. Haz clic en **Save**. La app se reiniciara automaticamente.

### Limitaciones de Streamlit Cloud

- 1 GB de RAM (puede ser justo para ML engine)
- La app se duerme tras 7 dias sin actividad (se despierta al visitar)
- No hay acceso SSH al servidor
- Base de datos SQLite se reinicia en cada despliegue

---

## Opcion 2: Hugging Face Spaces (GRATIS, mas potente)

Mas recursos que Streamlit Cloud, soporta Docker para control total.

### Paso 1: Crear cuenta en Hugging Face

1. Ve a https://huggingface.co/join
2. Crea tu cuenta

### Paso 2: Crear un Space

1. Ve a https://huggingface.co/new-space
2. Configura:
   - **Space name**: `quantum-retail-terminal`
   - **License**: MIT (o la que prefieras)
   - **SDK**: Docker
   - **Hardware**: CPU basic (gratis)
3. Haz clic en **Create Space**

### Paso 3: Subir el codigo

Opcion A — Desde la interfaz web:
1. Sube todos los archivos del proyecto al Space

Opcion B — Via Git (recomendado):
```bash
git clone https://huggingface.co/spaces/TU-USUARIO/quantum-retail-terminal
cd quantum-retail-terminal
# Copia todos los archivos del proyecto aqui
cp -r /ruta/a/tu/proyecto/* .
git add -A
git commit -m "Initial deployment"
git push
```

### Paso 4: Configurar Secrets

1. En tu Space, ve a **Settings**
2. En la seccion **Repository secrets**, agrega cada key:
   - Name: `FRED_API_KEY` / Value: tu key
   - Name: `GROQ_API_KEY` / Value: tu key
   - Name: `GEMINI_API_KEY` / Value: tu key
   - Name: `OPENROUTER_API_KEY` / Value: tu key

Los secrets estaran disponibles como variables de entorno. Si tu app usa `st.secrets`, necesitaras adaptarla para leer tambien de `os.environ`.

### Paso 5: Verificar despliegue

1. Espera a que el build termine (visible en la pestana **Logs**)
2. Tu app estara en: `https://huggingface.co/spaces/TU-USUARIO/quantum-retail-terminal`

### Archivos necesarios

El proyecto ya incluye:
- `Dockerfile` — configurado para HF Spaces (puerto 7860, usuario non-root)
- `README.md` — con frontmatter YAML para HF Spaces
- `.dockerignore` — excluye archivos innecesarios

---

## Opcion 3: Oracle Cloud Free Tier (GRATIS, servidor dedicado)

Servidor VPS gratuito de por vida con Oracle Cloud. Ideal para uso permanente.

### Paso 1: Crear cuenta Oracle Cloud

1. Ve a https://cloud.oracle.com
2. Crea una cuenta (requiere tarjeta de credito, pero NO se cobra)
3. Selecciona tu region (recomendado: una cercana a ti)

### Paso 2: Crear instancia VM

1. Ve a **Compute** > **Instances** > **Create Instance**
2. Configura:
   - **Shape**: VM.Standard.A1.Flex (ARM, Always Free)
   - **OCPU**: 2 (maximo gratis: 4)
   - **Memory**: 12 GB (maximo gratis: 24 GB)
   - **Image**: Ubuntu 22.04 Minimal
   - **Networking**: Crea una VCN publica
3. Descarga tu SSH key o sube la tuya
4. Haz clic en **Create**

### Paso 3: Configurar Security List (abrir puerto)

1. Ve a **Networking** > **Virtual Cloud Networks** > tu VCN
2. Haz clic en tu **Subnet**
3. Haz clic en tu **Security List**
4. Agrega una **Ingress Rule**:
   - Source CIDR: `0.0.0.0/0`
   - Destination Port Range: `8501`
   - Protocol: TCP
5. Guarda

### Paso 4: Ejecutar script de setup

Conectate a tu instancia por SSH y ejecuta:

```bash
ssh -i tu-key.pem ubuntu@IP-DE-TU-INSTANCIA

# Descargar y ejecutar el script
curl -O https://raw.githubusercontent.com/carlos060798/terminal-de-inverisones-y-trading/main/deploy/deploy_oracle.sh
sudo bash deploy_oracle.sh
```

O manualmente:
```bash
sudo bash deploy/deploy_oracle.sh
```

### Paso 5: Configurar API keys

```bash
sudo nano /home/quantum/app/.streamlit/secrets.toml
```

Agrega tus keys y guarda. Luego reinicia:
```bash
sudo systemctl restart quantum-terminal
```

### Paso 6: Verificar

Abre en tu navegador: `http://IP-DE-TU-INSTANCIA:8501`

### Paso 7: Configurar dominio (opcional)

Si tienes un dominio propio:
```bash
# Instalar Nginx como reverse proxy
sudo apt install -y nginx certbot python3-certbot-nginx

# Crear configuracion Nginx
sudo cat > /etc/nginx/sites-available/quantum << 'NGINX'
server {
    listen 80;
    server_name tudominio.com;

    location / {
        proxy_pass http://localhost:8501;
        proxy_http_version 1.1;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection "upgrade";
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_read_timeout 86400;
    }

    location /_stcore/stream {
        proxy_pass http://localhost:8501/_stcore/stream;
        proxy_http_version 1.1;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection "upgrade";
        proxy_read_timeout 86400;
    }
}
NGINX

sudo ln -sf /etc/nginx/sites-available/quantum /etc/nginx/sites-enabled/
sudo nginx -t && sudo systemctl reload nginx

# Obtener certificado SSL
sudo certbot --nginx -d tudominio.com
```

---

## Opcion 4: Hetzner / VPS generico ($4/mes)

Para cualquier VPS con Ubuntu/Debian (Hetzner, DigitalOcean, Linode, Vultr, etc).

### Paso 1: Crear servidor

1. Crea una cuenta en https://www.hetzner.com/cloud (o tu proveedor preferido)
2. Crea un servidor:
   - **OS**: Ubuntu 22.04
   - **Type**: CX11 (2 vCPU, 2 GB RAM) — desde ~$4/mes
   - **Location**: la mas cercana a ti
3. Anota la IP y configura SSH

### Paso 2: Ejecutar script de setup

```bash
ssh root@IP-DE-TU-SERVIDOR

# Descargar y ejecutar
curl -O https://raw.githubusercontent.com/carlos060798/terminal-de-inverisones-y-trading/main/deploy/deploy_hetzner.sh
sudo bash deploy_hetzner.sh
```

### Paso 3: Configurar API keys

```bash
sudo nano /home/quantum/app/.streamlit/secrets.toml
```

Agrega tus keys, guarda, y reinicia:
```bash
sudo systemctl restart quantum-terminal
```

### Paso 4: Configurar dominio + SSL (recomendado)

```bash
sudo apt install -y nginx certbot python3-certbot-nginx
```

Sigue los mismos pasos de Nginx del Paso 7 de Oracle Cloud.

### Paso 5: Verificar

Abre `http://IP-DE-TU-SERVIDOR:8501` (o tu dominio si configuraste Nginx).

---

## Configuracion de Secrets

Todas las plataformas necesitan las mismas API keys. Formato `.streamlit/secrets.toml`:

```toml
FRED_API_KEY = "tu-fred-key"
GROQ_API_KEY = "tu-groq-key"
OPENROUTER_API_KEY = "tu-openrouter-key"
GEMINI_API_KEY = "tu-gemini-key"
```

### Donde obtener cada key

| Key | URL | Costo |
|-----|-----|-------|
| FRED_API_KEY | https://fred.stlouisfed.org/docs/api/api_key.html | Gratis |
| GROQ_API_KEY | https://console.groq.com | Gratis |
| GEMINI_API_KEY | https://aistudio.google.com/apikey | Gratis |
| OPENROUTER_API_KEY | https://openrouter.ai/keys | Gratis (con limites) |

---

## Solucion de Problemas

### La app no inicia

```bash
# Ver logs del servicio
sudo journalctl -u quantum-terminal -f

# Verificar que el servicio esta activo
sudo systemctl status quantum-terminal

# Reiniciar
sudo systemctl restart quantum-terminal
```

### Error de dependencias

```bash
# Activar el entorno virtual y reinstalar
su - quantum
cd app
source venv/bin/activate
pip install --upgrade pip
pip install -r requirements.txt
```

### Puerto bloqueado (Oracle Cloud)

Oracle Cloud tiene doble firewall: iptables en la VM Y Security Lists en la consola web. Asegurate de abrir el puerto en AMBOS:

```bash
# En la VM
sudo iptables -I INPUT -p tcp --dport 8501 -j ACCEPT
sudo netfilter-persistent save
```

Y en la consola de Oracle Cloud: Networking > VCN > Subnet > Security List > agregar Ingress Rule para puerto 8501.

### La app se duerme (Streamlit Cloud)

Esto es normal en el plan gratuito. La app se despierta automaticamente cuando alguien la visita. Para evitarlo, puedes usar un servicio de uptime monitoring (como UptimeRobot) que haga ping cada 5 minutos.

### Error de memoria

Si la app se queda sin memoria:
- Desactiva el ML engine (requiere mas RAM)
- En Oracle Cloud, aumenta la memoria de la instancia (hasta 24 GB gratis)
- En Streamlit Cloud, considera migrar a otra plataforma

### Base de datos se reinicia

En Streamlit Cloud y HF Spaces, la base de datos SQLite no persiste entre despliegues. Para persistencia, usa Oracle Cloud o un VPS.

---

## Actualizar la Aplicacion

### Streamlit Cloud

Hace pull automaticamente al hacer push a `main`. Solo haz:
```bash
git add -A
git commit -m "Update"
git push
```

### Hugging Face Spaces

Igual que Streamlit Cloud si conectaste el repo de GitHub. Si subiste manualmente, repite el proceso de subida.

### Oracle Cloud / VPS

```bash
ssh -i tu-key.pem ubuntu@IP-DE-TU-INSTANCIA

# Actualizar codigo
su - quantum
cd app
git pull origin main

# Actualizar dependencias (si cambiaron)
source venv/bin/activate
pip install -r requirements.txt

# Reiniciar
exit
sudo systemctl restart quantum-terminal
```

---

## Comparacion de Plataformas

| Caracteristica | Streamlit Cloud | HF Spaces | Oracle Cloud | Hetzner VPS |
|---|---|---|---|---|
| Costo | Gratis | Gratis | Gratis | ~$4/mes |
| RAM | 1 GB | 2 GB | Hasta 24 GB | 2-16 GB |
| Setup | 2 min | 5 min | 30 min | 20 min |
| Dificultad | Muy facil | Facil | Media | Media |
| Dominio custom | No | No | Si | Si |
| DB persistente | No | No | Si | Si |
| SSL incluido | Si | Si | Manual | Manual |
| Uptime | Se duerme | Siempre on | Siempre on | Siempre on |
| ML Engine | Limitado | OK | Excelente | Depende plan |
