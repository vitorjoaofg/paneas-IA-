const puppeteer = require('puppeteer-extra');
const StealthPlugin = require('puppeteer-extra-plugin-stealth');
const fs = require('fs');
puppeteer.use(StealthPlugin());

const delay = (ms) => new Promise(resolve => setTimeout(resolve, ms));

(async () => {
    const empresa = (process.env.EMPRESA || 'claro').toLowerCase();
    const PROCESSOS_PARALELOS = parseInt(process.env.PARALELISMO || '5', 10);
    const arquivoLista = `processos_lista_${empresa}.json`;
    const arquivoSaida = `processos_completos_${empresa}.json`;
    const LIMITE_PROCESSOS = parseInt(process.env.LIMITE_DETALHES || '0', 10);

    console.log(`🏢 Empresa: ${empresa}`);
    console.log(`📂 Arquivo entrada: ${arquivoLista}`);
    console.log(`💾 Arquivo saída: ${arquivoSaida}\n`);
    
    // Carregar lista de processos
    if (!fs.existsSync(arquivoLista)) {
        console.error(`❌ Arquivo ${arquivoLista} não encontrado!`);
        console.log(`Execute primeiro: EMPRESA=${empresa} node coletar-lista.js`);
        process.exit(1);
    }

    let processos = JSON.parse(fs.readFileSync(arquivoLista, 'utf8'));
    console.log(`📂 Carregados ${processos.length} processos\n`);

    let existentes = [];
    if (fs.existsSync(arquivoSaida)) {
        try {
            existentes = JSON.parse(fs.readFileSync(arquivoSaida, 'utf8'));
            console.log(`📥 Mesclando ${existentes.length} registros já enriquecidos\n`);
        } catch (err) {
            console.warn('⚠️  Não foi possível ler processos_completos.json, criando do zero.');
            existentes = [];
        }
    }

    const mapaExistentes = new Map(existentes.map(p => [p.numero, p]));
    processos = processos.map(p => {
        const existente = mapaExistentes.get(p.numero);
        if (existente) {
            return {
                ...p,
                detalhesColetados: existente.detalhesColetados,
                detalhesColetadosEm: existente.detalhesColetadosEm,
                detalhesPublicos: existente.detalhesPublicos
            };
        }
        return p;
    });

    // Filtrar apenas os que não têm detalhes
    let processosSemDetalhes = processos.filter(p => !p.detalhesColetados);
    if (LIMITE_PROCESSOS > 0 && processosSemDetalhes.length > LIMITE_PROCESSOS) {
        processosSemDetalhes = processosSemDetalhes.slice(0, LIMITE_PROCESSOS);
        console.log(`⚠️  Limitando processamento aos primeiros ${LIMITE_PROCESSOS} processos para testes.`);
    }
    console.log(`🔍 ${processosSemDetalhes.length} processos precisam de detalhes\n`);

    if (processosSemDetalhes.length === 0) {
        console.log('✅ Todos os processos já têm detalhes!');
        process.exit(0);
    }

    const browser = await puppeteer.launch({
        headless: false,  // Site do TJRJ pode bloquear headless mode
        args: [
            '--no-sandbox',
            '--disable-setuid-sandbox',
            '--disable-dev-shm-usage'
        ]
    });

    const paginasPool = [];
    let totalProcessado = 0;

    const salvarArquivo = () => {
        fs.writeFileSync(arquivoSaida, JSON.stringify(processos, null, 2));
    };

    // Criar pool
    console.log(`🔧 Criando pool de ${PROCESSOS_PARALELOS} páginas...`);
    for (let i = 0; i < PROCESSOS_PARALELOS; i++) {
        const page = await browser.newPage();

        // Bloqueio de recursos desabilitado para compatibilidade com headless mode
        // TODO: Re-enable seletivamente depois de testar
        // await page.setRequestInterception(true);

        await page.evaluateOnNewDocument(() => {
            Object.defineProperty(navigator, 'webdriver', { get: () => false });
            window.chrome = { runtime: {} };
        });

        await page.setViewport({ width: 1779, height: 1698 });
        await page.setUserAgent('Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/127.0.0.0 Safari/537.36');

        await page.goto('https://tjrj.pje.jus.br/pje/ConsultaPublica/listView.seam', {
            waitUntil: 'domcontentloaded',
            timeout: 30000
        });

        // Aguardar campo de busca estar disponível (sem delay fixo)
        await page.waitForSelector('#fPP\\:numProcesso-inputNumeroProcessoDecoration\\:numProcesso-inputNumeroProcesso', { timeout: 10000 }).catch(() => {});

        paginasPool.push({ page, emUso: false });
        console.log(`   ✓ Página ${i + 1}/${PROCESSOS_PARALELOS}`);
    }
    console.log('✅ Pool criado!\n');

    const pegarPagina = async () => {
        while (true) {
            const paginaLivre = paginasPool.find(p => !p.emUso);
            if (paginaLivre) {
                paginaLivre.emUso = true;
                return paginaLivre;
            }
            await new Promise(resolve => setTimeout(resolve, 100));
        }
    };

    const liberarPagina = (paginaObj) => {
        paginaObj.emUso = false;
    };

    const esperarPopupDo = async (origPage, timeout = 20000) => {
        try {
            const target = await browser.waitForTarget(
                t => t.opener() && t.opener()._targetId === origPage.target()._targetId,
                { timeout }
            );
            const page = await target.page();
            return page;
        } catch (err) {
            throw new Error('Popup não abriu');
        }
    };

    const buscarDetalhes = async (processo, index, total) => {
        let paginaObj = null;
        let detalhePage = null;

        try {
            paginaObj = await pegarPagina();

            // Recriar página se foi fechada
            if (!paginaObj.page || paginaObj.page.isClosed()) {
                paginaObj.page = await browser.newPage();

                await paginaObj.page.evaluateOnNewDocument(() => {
                    Object.defineProperty(navigator, 'webdriver', { get: () => false });
                    window.chrome = { runtime: {} };
                });

                await paginaObj.page.setViewport({ width: 1779, height: 1698 });
                await paginaObj.page.setUserAgent('Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/127.0.0.0 Safari/537.36');

                await paginaObj.page.goto('https://tjrj.pje.jus.br/pje/ConsultaPublica/listView.seam', {
                    waitUntil: 'domcontentloaded',
                    timeout: 30000
                });
                await paginaObj.page.waitForSelector('#fPP\\:numProcesso-inputNumeroProcessoDecoration\\:numProcesso-inputNumeroProcesso', { timeout: 10000 }).catch(() => {});
            }

            const consultaPage = paginaObj.page;
            
            const urlAtual = consultaPage.url();
            if (!urlAtual.includes('ConsultaPublica/listView')) {
                await consultaPage.goto('https://tjrj.pje.jus.br/pje/ConsultaPublica/listView.seam', {
                    waitUntil: 'domcontentloaded',
                    timeout: 30000
                });
                // Aguardar campo de busca estar pronto
                await consultaPage.waitForSelector('#fPP\\:numProcesso-inputNumeroProcessoDecoration\\:numProcesso-inputNumeroProcesso', { timeout: 10000 });
            }

            const seletorNumero = '#fPP\\:numProcesso-inputNumeroProcessoDecoration\\:numProcesso-inputNumeroProcesso';
            await consultaPage.waitForSelector(seletorNumero, { timeout: 15000 });
            await consultaPage.evaluate((selector) => {
                const campo = document.querySelector(selector);
                if (campo) {
                    campo.value = '';
                    campo.dispatchEvent(new Event('input', { bubbles: true }));
                    campo.dispatchEvent(new Event('change', { bubbles: true }));
                }
            }, seletorNumero);

            await consultaPage.type(seletorNumero, processo.numero, { delay: 30 });
            await consultaPage.click('#fPP\\:searchProcessos');

            // Aguardar resultados aparecerem (sem delay fixo)
            let encontrouLinha = true;
            try {
                await consultaPage.waitForFunction(() => {
                    const tabela = document.querySelector('#fPP\\:processosTable\\:tb');
                    return tabela && tabela.querySelectorAll('tr').length > 0;
                }, { timeout: 12000 });
            } catch (err) {
                encontrouLinha = false;
            }

            if (!encontrouLinha) {
                throw new Error('Processo não encontrado na consulta pública');
            }

            const urlDepoisBusca = consultaPage.url();
            if (urlDepoisBusca.includes('login') || urlDepoisBusca.includes('expired')) {
                throw new Error('Sessão expirou');
            }
            
            await consultaPage.bringToFront();
            const botaoDetalhes = await consultaPage.$('a[title="Ver Detalhes"]');
            if (!botaoDetalhes) {
                throw new Error('Botão de detalhes não encontrado');
            }

            // Extrair URL do popup antes de clicar (mais rápido e confiável)
            const fallbackUrl = await consultaPage.evaluate(() => {
                const btn = document.querySelector('a[title="Ver Detalhes"]');
                if (!btn) return null;
                const onclick = btn.getAttribute('onclick');
                if (!onclick) return null;
                const match = onclick.match(/'([^']+DetalheProcessoConsultaPublica[^']+)'/);
                return match ? match[1] : null;
            });

            let popupErro = false;
            try {
                const popupPromise = esperarPopupDo(consultaPage, 15000);
                await botaoDetalhes.click({ delay: 30 });
                detalhePage = await popupPromise;
            } catch (popupError) {
                popupErro = true;
            }

            // Fallback: usar URL extraída diretamente
            if ((popupErro || !detalhePage) && fallbackUrl) {
                try {
                    const popupPromise = esperarPopupDo(consultaPage, 12000);
                    await consultaPage.evaluate((url) => window.open(url, '_blank'), fallbackUrl);
                    detalhePage = await popupPromise;
                } catch (err) {
                    // Se ambos falharem, erro será tratado abaixo
                }
            }

            if (!detalhePage) {
                throw new Error('Popup não abriu');
            }

            await detalhePage.bringToFront();

            // Aguardar conteúdo estar realmente carregado (não apenas elemento vazio)
            await detalhePage.waitForSelector('#pageBody', { timeout: 15000 });
            await detalhePage.waitForFunction(() => {
                const pageBody = document.querySelector('#pageBody');
                return pageBody && pageBody.innerText.trim().length > 100;
            }, { timeout: 10000 }).catch(() => {
                // Se timeout, tentar extrair mesmo assim
            });

            const detalhes = await detalhePage.evaluate(() => {
                const dados = {};
                const pageBody = document.querySelector('#pageBody');
                if (!pageBody) return { erro: 'Página não carregada' };
                
                const labels = document.querySelectorAll('label, .label, strong, b, dt');
                const infos = {};
                
                labels.forEach(label => {
                    const texto = label.innerText.trim();
                    const proximo = label.nextElementSibling || label.parentElement.nextElementSibling;
                    if (proximo && texto) {
                        infos[texto] = proximo.innerText.trim();
                    }
                });
                
                dados.informacoes = infos;
                
                const movimentacoes = [];
                const movRows = document.querySelectorAll('table tbody tr');
                movRows.forEach(row => {
                    const cols = row.querySelectorAll('td');
                    if (cols.length >= 2) {
                        movimentacoes.push({
                            data: cols[0]?.innerText.trim(),
                            descricao: cols[1]?.innerText.trim()
                        });
                    }
                });
                dados.movimentacoes = movimentacoes;
                
                return dados;
            });

            processo.detalhesPublicos = detalhes;
            processo.detalhesColetados = true;
            processo.detalhesColetadosEm = new Date().toISOString();
            
            console.log(`   ✅ [${index}/${total}] ${processo.numero}`);
            return true;
            
        } catch (error) {
            console.log(`   ❌ [${index}/${total}] ${processo.numero} - ${error.message}`);
            processo.detalhesPublicos = { erro: error.message };
            processo.detalhesColetados = false;
            return false;
        } finally {
            // Fechar popup E a aba de consulta - próxima aba vem pra frente automaticamente
            if (detalhePage) await detalhePage.close().catch(() => {});
            if (paginaObj && paginaObj.page) {
                await paginaObj.page.close().catch(() => {});
                paginaObj.page = null; // Marcar como fechada
            }
            if (paginaObj) liberarPagina(paginaObj);
        }
    };

    try {
        const inicio = Date.now();
        
        for (let i = 0; i < processosSemDetalhes.length; i += PROCESSOS_PARALELOS) {
            const batch = processosSemDetalhes.slice(i, i + PROCESSOS_PARALELOS);
            
            console.log(`\n🚀 Batch ${Math.floor(i / PROCESSOS_PARALELOS) + 1}: ${batch.length} processos...`);
            
            const promises = batch.map((proc, idx) => 
                buscarDetalhes(proc, i + idx + 1, processosSemDetalhes.length)
            );
            
            await Promise.all(promises);
            
            totalProcessado += batch.length;
            salvarArquivo();
            
            const sucessoBatch = batch.filter(p => p.detalhesColetados).length;
            console.log(`💾 Salvos! Total: ${totalProcessado}/${processosSemDetalhes.length} | ✓ ${sucessoBatch}`);

            // Pausa curta entre batches (evitar sobrecarga)
            await new Promise(resolve => setTimeout(resolve, 500));
        }

        const fim = Date.now();
        const tempo = ((fim - inicio) / 1000 / 60).toFixed(2);

        console.log('\n' + '='.repeat(60));
        console.log('🎉 ENRIQUECIMENTO CONCLUÍDO!');
        console.log('='.repeat(60));
        console.log(`⏱️  Tempo: ${tempo} min`);
        console.log(`💾 Arquivo: ${arquivoSaida}`);
        
        const comSucesso = processos.filter(p => p.detalhesColetados).length;
        console.log(`✓ Com detalhes: ${comSucesso}/${processos.length}`);
        console.log('='.repeat(60));
        
    } catch (error) {
        console.error('❌ Erro:', error.message);
        salvarArquivo();
    } finally {
        await browser.close();
    }

})().catch(err => {
    console.error(err);
    process.exit(1);
});
