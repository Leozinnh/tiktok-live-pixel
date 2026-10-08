"""As frases que o Narrador fala: a do presente e a da chegada.

A live nao pode soar repetitiva: se todo presente virasse sempre o mesmo
"obrigado pelo presente" — e toda chegada o mesmo "bem-vindo" — o audio
viraria ruido de fundo. O Narrador SORTEIA uma frase da lista certa a cada
evento, entao dezenas de falas diferentes se alternam sozinhas sem ninguem
escrever logica de rodizio.

`FALAS` e a lista do presente. Toda frase recebe tres valores:

- `{nome}`: quem mandou o presente, sem o arroba.
- `{quantidade}`: ja formatada — "5x " — e VAZIA quando e um presente so,
  porque "1x Rose" nao existe na lingua falada.
- `{presente}`: o nome do presente, como o TikTok manda ("Rose", "Galaxy").

Escreva pensando nos dois casos: "mandou {quantidade}{presente}" le bem
tanto como "mandou Rose" quanto como "mandou 5x Rose" — e o texto vai para
a voz, entao acento e pontuacao importam (e o que faz a Francisca falar
certo).

`BOAS_VINDAS` e a lista da chegada, e so recebe `{nome}`: a chegada nao tem
quantidade nem presente — o que ela tem e a pessoa, e a frase inteira gira
em torno do nome dela.

Quem quiser trocar as frases sem mexer no codigo aponta `tts.falas` — e
`tts.boas_vindas` — no `config.json` para as proprias listas; as daqui sao o
padrao do jogo.
"""

FALAS = [
    # --- Originais ---
    "Olha o presente! {nome} mandou {quantidade}{presente}! Valeu, família!",
    "Aeee! {nome} mandou {quantidade}{presente}! Valeu demais, família!",
    "Presente na área! {nome} mandou {quantidade}{presente}! Valeu!",
    "Olha isso, família! {nome} mandou {quantidade}{presente}! Muito obrigado!",
    "É presente! Obrigado, {nome}! {quantidade}{presente} no jogo!",
    "{nome} mandou {quantidade}{presente}! Você é incrível, valeu!",
    "Mais um presente! {nome} mandou {quantidade}{presente}! Valeeeu!",
    "Obrigado, {nome}! {quantidade}{presente} para pintar o mundo!",
    "{nome} chegou com {quantidade}{presente}! Valeu, família!",
    "Uhuu! Chegou {quantidade}{presente}! Obrigado, {nome}!",
    "Que presenteza! {nome} mandou {quantidade}{presente}! Valeu demais!",
    "Olha o carinho! {nome} mandou {quantidade}{presente}! Gratidão, família!",
    "{nome} mandou {quantidade}{presente}! Isso enche a tela de pixel!",
    "Aí sim, {nome}! {quantidade}{presente} no jogo! Muito obrigado!",
    "Gratidão, {nome}! {quantidade}{presente} na área para a família!",
    "Família, chegou presente! {nome} mandou {quantidade}{presente}! Valeu!",
    "Valeu, {nome}! {quantidade}{presente} recebido com muito carinho!",
    "{nome} mandou {quantidade}{presente}! Obrigado, obrigado, obrigado!",
    "Presente novo na tela! {nome} mandou {quantidade}{presente}! Valeu, família!",
    "É presente novo! {nome} mandou {quantidade}{presente}! Muito obrigado!",
    "Família, olha o presente! {nome} mandou {quantidade}{presente}! Valeu!",
    "Que alegria! {nome} mandou {quantidade}{presente}! Obrigado, família!",
    "{nome} mandou {quantidade}{presente}! Que presente bom! Valeu!",
    "Olha a força da família! {nome} mandou {quantidade}{presente}! Valeu demais!",

    # --- Empolgadas ---
    "Eita! {nome} mandou {quantidade}{presente}! Que loucura, valeu!",
    "Uau! {nome} mandou {quantidade}{presente}! Você mandou muito bem, obrigado!",
    "Explodiu a live! {nome} mandou {quantidade}{presente}! Valeu, família!",
    "Haja coração! {nome} mandou {quantidade}{presente}! Muito obrigado!",
    "Socorro, que presente! {nome} mandou {quantidade}{presente}! Valeu demais!",
    "Chegou chegando! {nome} mandou {quantidade}{presente}! Obrigadão!",
    "Pelo amor! {nome} mandou {quantidade}{presente}! Você é demais!",
    "Gente, olha isso! {nome} mandou {quantidade}{presente}! Valeu, valeu, valeu!",
    "Bora, bora, bora! {nome} mandou {quantidade}{presente}! Obrigado!",
    "Que isso, {nome}! {quantidade}{presente} na live! Valeu de coração!",
    "Tá pegando fogo! {nome} mandou {quantidade}{presente}! Obrigado, família!",
    "Respeita o {nome}! Mandou {quantidade}{presente}! Valeu demais!",
    "Chuva de carinho! {nome} mandou {quantidade}{presente}! Muito obrigado!",
    "Que cena linda! {nome} mandou {quantidade}{presente}! Gratidão!",
    "Ai, ai, ai! {nome} mandou {quantidade}{presente}! Valeu, família!",
    "É hoje! {nome} mandou {quantidade}{presente}! Obrigado de verdade!",
    "Vish, {nome}! {quantidade}{presente} na tela! Valeu demais!",
    "Que presentão! {nome} mandou {quantidade}{presente}! Muito obrigado!",
    "Isso é amor! {nome} mandou {quantidade}{presente}! Valeu, família!",
    "Salve, {nome}! {quantidade}{presente} caiu aqui! Obrigadão!",

    # --- Carinhosas ---
    "Que coração bonito, {nome}! {quantidade}{presente}! Muito obrigado!",
    "Você faz a live brilhar, {nome}! Valeu pelo presente {quantidade}{presente}!",
    "Recebi com um sorriso! {nome} mandou {quantidade}{presente}! Gratidão!",
    "Obrigado pelo carinho, {nome}! {quantidade}{presente} é demais!",
    "Que gesto lindo! {nome} mandou {quantidade}{presente}! Valeu, de coração!",
    "Você é gente fina, {nome}! {quantidade}{presente} recebido! Obrigado!",
    "Isso aquece o coração! {nome} mandou {quantidade}{presente}! Gratidão, família!",
    "Obrigado por estar aqui, {nome}! E ainda mandou {quantidade}{presente}!",
    "A live fica melhor com você, {nome}! Valeu pelo {quantidade}{presente}!",
    "Que carinho, {nome}! {quantidade}{presente} chegou! Muito obrigado!",
    "{nome}, você é show! {quantidade}{presente} recebido com muito amor!",
    "Que fofura, {nome}! Mandou {quantidade}{presente}! Valeu demais!",
    "Mil vezes obrigado, {nome}! {quantidade}{presente} é um carinho enorme!",
    "Família linda! {nome} mandou {quantidade}{presente}! Gratidão total!",
    "Que presente especial! {nome} mandou {quantidade}{presente}! Obrigado!",

    # --- Divertidas ---
    "Alô, alô! {nome} mandou {quantidade}{presente}! A conta do carinho está em dia!",
    "Quem mandou? Foi o {nome}! {quantidade}{presente} na área! Valeu!",
    "O {nome} não veio para brincar! Mandou {quantidade}{presente}! Obrigado!",
    "Pode aplaudir! {nome} mandou {quantidade}{presente}! Valeu, família!",
    "Tá chovendo presente! {nome} mandou {quantidade}{presente}! Obrigadão!",
    "Passando para dizer: {nome} mandou {quantidade}{presente}! Valeu demais!",
    "Os cavalos agradecem! {nome} mandou {quantidade}{presente}! Valeu!",
    "Atenção, atenção! {nome} mandou {quantidade}{presente}! Que moral!",
    "Tapete vermelho para o {nome}! Mandou {quantidade}{presente}! Obrigado!",
    "Chama a banda! {nome} mandou {quantidade}{presente}! Valeu, família!",
    "Cuidado, que o {nome} tá generoso! {quantidade}{presente} na live! Obrigado!",
    "O {nome} mandou {quantidade}{presente} e a live agradece! Valeu!",
    "Ding dong! Chegou {quantidade}{presente}! Obrigado, {nome}!",
    "Entrega especial para a live! {nome} mandou {quantidade}{presente}! Valeu!",
    "Isso é que é torcida! {nome} mandou {quantidade}{presente}! Muito obrigado!",
    "Aplausos para o {nome}! {quantidade}{presente} chegou! Valeu demais!",
    "Pode soltar o grito! {nome} mandou {quantidade}{presente}! Obrigadão!",
    "Esse {nome} é fora de série! {quantidade}{presente} na tela! Valeu!",

    # --- Curtas e diretas ---
    "Valeu, {nome}! {quantidade}{presente}!",
    "Obrigado, {nome}! {quantidade}{presente} na área!",
    "{nome}, muito obrigado pelo {quantidade}{presente}!",
    "Gratidão, {nome}! {quantidade}{presente}!",
    "Show, {nome}! {quantidade}{presente} recebido!",
    "É isso, {nome}! {quantidade}{presente}! Valeu!",
    "Boa, {nome}! {quantidade}{presente} no jogo!",
    "Top, {nome}! {quantidade}{presente}! Obrigado!",
    "Chegou {quantidade}{presente} do {nome}! Valeu!",
    "{nome} mandou {quantidade}{presente}! Valeu, valeu!",
    "Muito obrigado, {nome}! {quantidade}{presente} é demais!",
    "Que beleza! {quantidade}{presente} do {nome}! Obrigado!",
]

# --------------------------------------------------------------------------
# Boas-vindas
# --------------------------------------------------------------------------

BOAS_VINDAS = [
    # --- Originais ---
    "Olha quem chegou! {nome}, seja bem-vindo à live!",
    "{nome} chegou! Seja bem-vindo, família!",
    "Bem-vindo, {nome}! Aqui o seu pixel vira arte!",
    "{nome} entrou na live! Seja bem-vindo, família!",
    "E aí, {nome}! Bem-vindo! Escolhe uma cor e pinta com a gente!",

    # --- Empolgadas ---
    "Chegou mais um pintor! Bem-vindo, {nome}!",
    "Família crescendo! {nome} chegou! Seja bem-vindo!",
    "Salve, {nome}! Chegou na hora certa, a tela tá esperando você!",
    "{nome} na área! Bem-vindo à live! Pinta um pixel aí!",
    "Chegou o {nome}! Bem-vindo à família!",
    "Aeee! {nome} entrou! Bem-vindo, bora pintar!",
    "Uhuu! Olha o {nome} aqui! Seja muito bem-vindo!",
    "A live ficou melhor! {nome} chegou! Bem-vindo, família!",
    "Entrou o {nome}! Bem-vindo! Tá todo mundo animado aqui!",
    "Eita, chegou gente boa! Bem-vindo, {nome}!",
    "É isso! {nome} na live! Seja bem-vindo, bora fazer arte!",
    "Chegou chegando! {nome}, bem-vindo à tela mais colorida da internet!",
    "Mais um pra família! Bem-vindo, {nome}! Pega um pincel e vem!",
    "Boa! {nome} entrou! Bem-vindo, a tela é toda sua!",
    "Olha ele aí! {nome}, seja bem-vindo! Bora pintar!",

    # --- Carinhosas ---
    "Que bom te ver, {nome}! Bem-vindo!",
    "Bem-vindo, {nome}! Sua cor já tá te esperando!",
    "{nome}, seja bem-vindo! Vem pintar o mundo com a gente!",
    "Oi, {nome}! Que bom que você chegou! Bem-vindo!",
    "Bem-vindo, {nome}! A tela também é sua!",
    "Que alegria te receber, {nome}! Fica à vontade, a casa é sua!",
    "{nome}, seja muito bem-vindo! Aqui todo mundo é família!",
    "Oi, {nome}! Entra, senta aí e pinta com a gente! Bem-vindo!",
    "Que presença boa, {nome}! Bem-vindo à nossa live!",
    "Bem-vindo, {nome}! Obrigado por passar aqui e ficar com a gente!",
    "Que bom ter você aqui, {nome}! Seja bem-vindo, de coração!",
    "{nome}, a live ficou mais bonita com você! Bem-vindo!",
    "Seja bem-vindo, {nome}! Aqui tem um cantinho de tela só pra você!",
    "Olha que gente querida chegando! Bem-vindo, {nome}!",
    "Oi, {nome}! A família te recebe de braços abertos! Bem-vindo!",

    # --- Convidando a participar ---
    "Bem-vindo, {nome}! Manda um comentário e pinta um pixel!",
    "{nome}, chegou na hora boa! Escolhe uma cor e entra na arte!",
    "Seja bem-vindo, {nome}! Cada pixel seu conta na obra de hoje!",
    "Bem-vindo, {nome}! Vem fazer parte dessa pintura gigante!",
    "{nome}, bem-vindo! Que cor você vai deixar na tela hoje?",
    "Chegou o {nome}! Bem-vindo! A tela tá esperando o seu toque!",
    "Oi, {nome}! Bem-vindo! Bora deixar sua marca na tela!",
    "Bem-vindo, {nome}! Aqui todo mundo pinta junto, entra nessa!",
    "{nome}, seja bem-vindo! Um pixel de cada vez a gente faz arte!",
    "Bem-vindo, {nome}! Pega sua cor favorita e bora colorir!",

    # --- Divertidas ---
    "Atenção, atenção! {nome} acaba de entrar! Bem-vindo!",
    "Tapete vermelho pro {nome}! Seja bem-vindo à live!",
    "Chama a banda! O {nome} chegou! Bem-vindo!",
    "Alô, alô! Olha o {nome} na área! Seja bem-vindo!",
    "Ding dong! Chegou visita! Bem-vindo, {nome}!",
    "Quem chegou? Foi o {nome}! Seja bem-vindo, família!",
    "Pode aplaudir! {nome} entrou na live! Bem-vindo!",
    "O {nome} não perdeu a festa! Bem-vindo, bora pintar!",
    "Entrada triunfal do {nome}! Seja bem-vindo à live!",
    "Chegou o {nome} e a tela já tá sorrindo! Bem-vindo!",
    "Abram alas pro {nome}! Bem-vindo à live, família!",
    "Cuidado, artista chegando! Bem-vindo, {nome}!",

    # --- Curtas e diretas ---
    "Oi, {nome}! Bem-vindo à live!",
    "E chegou {nome}! Seja bem-vindo!",
    "Bem-vindo, {nome}! Pinta seu primeiro pixel!",
    "Olha o {nome} aí, gente! Bem-vindo à live!",
    "{nome}, bem-vindo! A família te espera!",
    "Seja bem-vindo, {nome}!",
    "Bem-vindo, {nome}! Fica com a gente!",
    "Fala, {nome}! Bem-vindo!",
    "Salve, {nome}! Bem-vindo à live!",
    "Boa, {nome}! Bem-vindo, família!",
    "Chegou, {nome}! Bem-vindo!",
    "{nome} na live! Bem-vindo!",
]