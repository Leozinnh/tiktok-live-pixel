
import asyncio
import edge_tts

TEXTO = """
E aí, galeraaa! Sejam muito bem-vindos ao PIXEL WORLD!

Aqui, quem manda na tela é vocês! Cada presente pode
transformar nossa tela e deixar a marca de quem está
participando!

Quer entrar no jogo? Manda uma rosa e você ganha um
pixel para pintar! Quer mandar aquele presentão?
Uma Galaxy vale sessenta pixels! É pixel pra caramba,
família!

Escolhe sua coordenada, acompanha a galera pintando
e vem fazer parte dessa disputa criativa!

Presta atenção na tela, porque podem rolar eventos
especiais, como o PIXEL TURBO, com multiplicadores
que deixam tudo ainda mais emocionante!

Não fica só olhando, não! Escolhe sua cor, manda
seu presente e deixa sua marca no PIXEL WORLD!

Quero ver quem vai dominar essa tela hoje!
Bora, família! Vamos pintar esse mundo juntos!

PIXEL WORLD! A tela é nossa!
"""

async def main():
    voz = edge_tts.Communicate(
        text=TEXTO,
        voice="pt-BR-FranciscaNeural",
        rate="+8%",
        pitch="+3Hz"
    )

    await voz.save("pixel_world_narracao.mp3")
    print("Narração gerada: pixel_world_narracao.mp3")

if __name__ == "__main__":
    asyncio.run(main())