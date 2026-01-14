# ia_treinos (treinos extras)

Esta pasta é para você colocar **novos treinos** sem mexer nas pastas das RNAs.

## Imagens (para treino_rna_qualquer_imagem)

Coloque imagens aqui:

- `ia_treinos/imagens/<ROTULO>/*.png|*.jpg|*.jpeg|*.webp|*.bmp`

Exemplo:

- `ia_treinos/imagens/maçã/1.jpg`
- `ia_treinos/imagens/maçã/2.png`
- `ia_treinos/imagens/cachorro/a.png`

Depois rode o hub:

```powershell
python main_ia.py
```

E clique em **Importar treinos extras (imagens)**.

## Endereços/URLs (opcional)

Você também pode criar um arquivo:

- `ia_treinos/enderecos.csv`

Formato:

```csv
label,ref
maçã,data:image/jpeg;base64,...
cachorro,https://site.com/dog.jpg
carro,C:\\imagens\\carro.png
```

O importador aceita `http(s)`, `data:image/...;base64,...`, `file:///...` e caminhos locais.

## Conversa (para rna_de_conversa)

Coloque treinos de conversa aqui:

- `ia_treinos/conversa/importar/*.txt` ou `*.jsonl`

Depois rode:

```powershell
python main_ia.py
```

E clique em **Importar treinos extras (conversa)**.
