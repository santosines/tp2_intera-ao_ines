import os
import random
from PIL import Image, ImageEnhance

diretorio = r'C:\Users\santo\Desktop\lic.icd\2025-2026\interação_modelos_larga_escala\TP2\data\images\violacao' 


imagens_atuais = [f for f in os.listdir(diretorio) if f.lower().endswith(('.png', '.jpg', '.jpeg'))]

quantidade_atual = len(imagens_atuais)
quantidade_desejada = 100
quantidade_faltante = quantidade_desejada - quantidade_atual

if quantidade_faltante <= 0:
    print("já tem 100 ou mais imagens na pasta,")
else:
    print(f"A gerar {quantidade_faltante} novas imagens para atingir 100.")
    
    for i in range(quantidade_faltante):
        imagem_escolhida = random.choice(imagens_atuais)
        caminho_imagem = os.path.join(diretorio, imagem_escolhida)
        img = Image.open(caminho_imagem)

        transformacao = random.choice(['espelhar', 'rotacionar', 'brilho'])

        if transformacao == 'espelhar':
            # inverte a imagem da esquerda para a direita
            img_modificada = img.transpose(Image.FLIP_LEFT_RIGHT)
            sufixo = "_espelhada"
            
        elif transformacao == 'rotacionar':
            # rotaciona levemente entre -15 e 15 graus
            angulo = random.randint(-15, 15)
            img_modificada = img.rotate(angulo)
            sufixo = f"_rot{angulo}"
            
        elif transformacao == 'brilho':
            # altera o brilho (0.8 é 20% mais escuro, 1.2 é 20% mais claro)
            fator = random.uniform(0.8, 1.2)
            realcador = ImageEnhance.Brightness(img)
            img_modificada = realcador.enhance(fator)
            sufixo = f"_brilho"

        nome_base, ext = os.path.splitext(imagem_escolhida)
        novo_nome = f"{nome_base}_aug_{i}{sufixo}{ext}"
        caminho_salvar = os.path.join(diretorio, novo_nome)

        if img_modificada.mode != 'RGB' and ext.lower() in ['.jpg', '.jpeg']:
            img_modificada = img_modificada.convert('RGB')

        img_modificada.save(caminho_salvar)

    print("Sucesso.")