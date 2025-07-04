# Dockerfile para a aplicação de videochamada Python

# 1. Usar uma imagem base oficial do Python
# Usar uma versão 'slim' para manter a imagem final pequena
FROM python:3.10-slim

# 2. Definir o diretório de trabalho dentro do contentor
WORKDIR /app

# 3. Copiar o ficheiro de dependências
# Copiar este ficheiro primeiro aproveita o cache do Docker. Se o ficheiro não mudar,
# o passo de instalação de dependências não será executado novamente.
COPY requirements.txt .

# 4. Instalar as dependências
# O --no-cache-dir garante que não guardamos o cache do pip, reduzindo o tamanho da imagem.
RUN pip install --no-cache-dir -r requirements.txt

# 5. Copiar o resto do código da aplicação para o diretório de trabalho
COPY . .

# 6. Expor a porta em que a aplicação corre
# O nosso server.py está configurado para correr na porta 8080
EXPOSE 8080

# 7. Definir o comando para executar a aplicação quando o contentor iniciar
CMD ["python", "server.py"]
