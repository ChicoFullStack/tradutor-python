# Dockerfile Otimizado para a aplicação de videochamada Python

# 1. Usar uma imagem base oficial do Python
# Usar uma versão 'slim' para manter a imagem final pequena
FROM python:3.10-slim

# 2. Definir variáveis de ambiente para boas práticas
#    - PYTHONUNBUFFERED: Garante que os outputs do Python são enviados diretamente para o terminal (bom para logs)
#    - PYTHONDONTWRITEBYTECODE: Impede o Python de escrever ficheiros .pyc
#    - PATH: Adiciona o ambiente virtual (venv) ao PATH do sistema
ENV PYTHONUNBUFFERED=1
ENV PYTHONDONTWRITEBYTECODE=1
ENV PATH="/venv/bin:$PATH"

# 3. Criar um utilizador não-root para segurança
#    Isto é feito antes de copiar o código para garantir que os ficheiros terão o dono correto.
RUN useradd -r -s /bin/false appuser

# 4. Definir o diretório de trabalho
WORKDIR /app

# 5. Criar e ativar um ambiente virtual
#    O diretório /venv será propriedade do root, mas o conteúdo será gerido pelo Python
RUN python -m venv /venv

# 6. Copiar o ficheiro de dependências
COPY requirements.txt .

# 7. Instalar as dependências no ambiente virtual
#    O venv já está no PATH, então o 'pip' correto será usado.
#    Isto é executado como root, conforme a recomendação para instalar pacotes a nível do sistema (dentro do venv).
RUN pip install --no-cache-dir -r requirements.txt

# 8. Copiar o resto do código da aplicação e dar posse ao novo utilizador não-root
COPY --chown=appuser:appuser . .

# 9. Mudar para o utilizador não-root para executar a aplicação
USER appuser

# 10. Expor a porta em que a aplicação corre
EXPOSE 8080

# 11. Definir o comando para executar a aplicação quando o contentor iniciar
CMD ["python", "server.py"]
