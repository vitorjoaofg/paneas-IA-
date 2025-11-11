const puppeteer = require('puppeteer-extra');
const StealthPlugin = require('puppeteer-extra-plugin-stealth');
const fs = require('fs');
puppeteer.use(StealthPlugin());

const delay = (ms) => new Promise(resolve => setTimeout(resolve, ms));

// Mapa de empresas
const EMPRESAS = {
    'claro': 'Claro S.A.',
    'azul': 'Azul Linhas Aéreas Brasileiras S.A.',
    'gol': 'Gol Linhas Aéreas S.A.',
    'latam': 'LATAM Airlines Group S.A.'
};

(async () => {
    const empresa = (process.env.EMPRESA || 'claro').toLowerCase();
    const termoBusca = EMPRESAS[empresa] || EMPRESAS['claro'];
    const arquivoSaida = `processos_lista_${empresa}.json`;

    console.log(`🏢 Empresa: ${termoBusca}`);
    console.log(`💾 Arquivo de saída: ${arquivoSaida}\n`);
    
    let todosProcessos = [];
    const numerosProcessosVistos = new Set();
    
    if (fs.existsSync(arquivoSaida)) {
        console.log('📂 Carregando arquivo existente...');
        todosProcessos = JSON.parse(fs.readFileSync(arquivoSaida, 'utf8'));
        todosProcessos.forEach(p => numerosProcessosVistos.add(p.numero));
        console.log(`   ✓ ${todosProcessos.length} processos já coletados\n`);
    }

    const browser = await puppeteer.launch({
        headless: false,
        args: ['--no-sandbox', '--disable-setuid-sandbox']
    });

    try {
        let page = await browser.newPage();
        await page.setViewport({ width: 1779, height: 1698 });
        page.setDefaultTimeout(15000);

        console.log('🔐 Login...');
        await page.goto('https://tjrj.pje.jus.br/pje/loginOld.seam', {
            waitUntil: 'domcontentloaded',
            timeout: 30000
        });

        await page.waitForSelector('#username');
        await page.type('#username', '48561184809', { delay: 30 });
        await page.type('#password', 'Julho3007!@', { delay: 30 });
        await Promise.all([
            page.waitForNavigation({ waitUntil: 'domcontentloaded', timeout: 30000 }),
            page.click('#btnEntrar')
        ]);

        console.log('✅ Logado!\n');

        const seletorNomeParte = '#fPP\\:j_id151\\:nomeParte';
        const seletorBotaoBuscar = '#fPP\\:searchProcessos';
        const seletorDataInicio = '#fPP\\:dataAutuacaoDecoration\\:dataAutuacaoInicioInputDate';
        const seletorDataInicioHidden = '#fPP\\:dataAutuacaoDecoration\\:dataAutuacaoInicioInputCurrentDate';
        const seletorDataFim = '#fPP\\:dataAutuacaoDecoration\\:dataAutuacaoFimInputDate';
        const seletorDataFimHidden = '#fPP\\:dataAutuacaoDecoration\\:dataAutuacaoFimInputCurrentDate';

        const parseDataBR = (texto) => {
            if (!texto || typeof texto !== 'string') return null;
            const partes = texto.split('/').map(p => parseInt(p, 10));
            if (partes.length !== 3 || partes.some(isNaN)) return null;
            const [dia, mes, ano] = partes;
            const data = new Date(ano, mes - 1, dia);
            return isNaN(data.getTime()) ? null : data;
        };

        const formatarDataBR = (data) => {
            if (!(data instanceof Date) || isNaN(data.getTime())) return null;
            const dia = String(data.getDate()).padStart(2, '0');
            const mes = String(data.getMonth() + 1).padStart(2, '0');
            const ano = data.getFullYear();
            return `${dia}/${mes}/${ano}`;
        };

        const navegarParaConsulta = async () => {
            console.log('📋 Navegando para consulta...');
            await page.waitForSelector('div.navbar-header > ul a', { visible: true });
            await page.click('div.navbar-header > ul a');
            await page.waitForSelector('#menu > div.nivel > ul > li:nth-of-type(1) > a', { visible: true, timeout: 10000 });
            await delay(500);
            await page.click('#menu > div.nivel > ul > li:nth-of-type(1) > a');
            await page.waitForSelector('#menu > div.nivel > ul > li:nth-of-type(1) > div > ul a', { visible: true, timeout: 10000 });
            await delay(500);
            await page.click('#menu > div.nivel > ul > li:nth-of-type(1) > div > ul a');
            await page.waitForSelector('#tabConsultaProcesso_lbl', { visible: true, timeout: 10000 });
            await delay(1000);
            await page.click('#tabConsultaProcesso_lbl');
            await page.waitForSelector('iframe', { timeout: 15000 });
            await delay(1000);
        };

        const atualizarIframe = async () => {
            const frames = page.frames();
            const alvo = frames.find(f => f.url().includes('consultaProcesso') || f.url().includes('ConsultaProcesso')) || frames[1];
            if (!alvo) {
                await navegarParaConsulta();
                const novosFrames = page.frames();
                const fallback = novosFrames.find(f => f.url().includes('consultaProcesso') || f.url().includes('ConsultaProcesso')) || novosFrames[1];
                if (!fallback) {
                    throw new Error('Iframe da consulta não encontrado após nova navegação');
                }
                return fallback;
            }
            return alvo;
        };

        await navegarParaConsulta();
        let iframe = await atualizarIframe();

        let filtroDataAutuacaoInicio = null;
        let filtroDataAutuacaoFim = null;
        const usarFiltroManual = process.env.FILTRO_DATA_MANUAL !== '0';

        if (todosProcessos.length > 0) {
            const datasValidas = todosProcessos
                .map(p => parseDataBR(p.dataAutuacao))
                .filter(data => data);
            if (datasValidas.length) {
                const maisAntiga = datasValidas.reduce((min, atual) => atual < min ? atual : min);
                filtroDataAutuacaoFim = formatarDataBR(maisAntiga);
                filtroDataAutuacaoInicio = '01/01/2000';
                console.log(`📅 Filtro sugerido: ${filtroDataAutuacaoInicio} → ${filtroDataAutuacaoFim}`);
            }
        }

        const preencherCampoData = async (selector, valor) => {
            await iframe.waitForSelector(selector, { timeout: 5000 });
            // Setar valor diretamente (sem digitar, para evitar problemas com máscara)
            await iframe.evaluate((sel, value) => {
                const input = document.querySelector(sel);
                if (input) {
                    input.value = value || '';
                    input.dispatchEvent(new Event('input', { bubbles: true }));
                    input.dispatchEvent(new Event('change', { bubbles: true }));
                    input.dispatchEvent(new Event('blur', { bubbles: true }));
                }
            }, selector, valor || '');
            await delay(200);
        };

        const aplicarFiltrosData = async () => {
            if (!filtroDataAutuacaoInicio && !filtroDataAutuacaoFim) {
                return;
            }
            if (filtroDataAutuacaoInicio !== null) {
                await preencherCampoData(seletorDataInicio, filtroDataAutuacaoInicio);
                // Não mexer no campo hidden - deixa o sistema preencher automaticamente
            }
            if (filtroDataAutuacaoFim !== null) {
                await preencherCampoData(seletorDataFim, filtroDataAutuacaoFim);
                // Não mexer no campo hidden - deixa o sistema preencher automaticamente
            }
            // Aguardar sistema processar as datas
            await delay(500);
        };

        const executarBusca = async ({ permitirManual = true } = {}) => {
            iframe = await atualizarIframe();
            await iframe.waitForSelector(seletorNomeParte, { timeout: 10000 });
            await iframe.evaluate((selector) => {
                const input = document.querySelector(selector);
                if (input) {
                    input.value = '';
                    input.dispatchEvent(new Event('input', { bubbles: true }));
                    input.dispatchEvent(new Event('change', { bubbles: true }));
                }
            }, seletorNomeParte);
            await iframe.type(seletorNomeParte, termoBusca, { delay: 50 });
            if (usarFiltroManual && permitirManual) {
                console.log('✋ Ajuste manualmente o intervalo de datas no navegador.');
                if (filtroDataAutuacaoInicio && filtroDataAutuacaoFim) {
                    console.log(`   Sugestão: ${filtroDataAutuacaoInicio} → ${filtroDataAutuacaoFim}`);
                }
                console.log('   Depois que os filtros estiverem certos, pressione Enter aqui no terminal para continuar.');
                await new Promise(resolve => {
                    process.stdin.resume();
                    process.stdin.once('data', () => {
                        process.stdin.pause();
                        resolve();
                    });
                });
            } else {
                await aplicarFiltrosData();
                const valoresDatas = await iframe.evaluate((cfg) => {
                    const ler = (sel) => document.querySelector(sel)?.value || '';
                    return {
                        inicio: ler(cfg.inicio),
                        fim: ler(cfg.fim)
                    };
                }, { inicio: seletorDataInicio, fim: seletorDataFim });
                console.log('📋 Datas aplicadas:', valoresDatas);
            }
            await iframe.click(seletorBotaoBuscar);
            // Aguardar tabela de resultados aparecer (sem delay fixo)
            await page.waitForFunction(() => {
                const frames = window.frames;
                for (let i = 0; i < frames.length; i++) {
                    try {
                        const tbody = frames[i].document.querySelector('#fPP\\:processosTable\\:tb');
                        if (tbody && tbody.querySelectorAll('tr.rich-table-row').length > 0) {
                            return true;
                        }
                    } catch(e) {}
                }
                return false;
            }, { timeout: 15000 }).catch(() => {});
            await delay(1000);
            iframe = await atualizarIframe();
        };

        const recarregarConsulta = async () => {
            await navegarParaConsulta();
            iframe = await atualizarIframe();
            await executarBusca({ permitirManual: false });
        };

        await executarBusca();

        const extrairProcessos = async () => {
            return await iframe.evaluate(() => {
                const dados = [];
                const tbody = document.querySelector('#fPP\\:processosTable\\:tb');
                if (!tbody) return dados;
                
                tbody.querySelectorAll('tr.rich-table-row').forEach((row) => {
                    const cols = row.querySelectorAll('td.rich-table-cell');
                    if (cols.length >= 10) {
                        const numeroLink = cols[1]?.querySelector('a');
                        const numero = numeroLink?.getAttribute('title') || numeroLink?.innerText.trim();
                        
                        if (numero && numero.match(/\d{7}-\d{2}\.\d{4}\.\d\.\d{2}\.\d{4}/)) {
                            dados.push({
                                numero,
                                orgaoJulgador: cols[3]?.innerText.trim() || '',
                                dataAutuacao: cols[4]?.innerText.trim() || '',
                                classeJudicial: cols[5]?.innerText.trim() || '',
                                autor: cols[6]?.innerText.trim() || '',
                                reu: cols[7]?.innerText.trim() || '',
                                localizacao: cols[8]?.innerText.trim() || '',
                                ultimaMovimentacao: cols[9]?.innerText.trim() || '',
                                coletadoEm: new Date().toISOString(),
                                detalhesColetados: false
                            });
                        }
                    }
                });
                return dados;
            });
        };

        const getPaginaAtual = async () => {
            return await iframe.evaluate(() => {
                const ativa = document.querySelector('tfoot td.rich-datascr-act');
                return ativa ? parseInt(ativa.innerText.trim()) : null;
            });
        };

        const getPrimeiroNumeroTabela = async () => {
            return await iframe.evaluate(() => {
                const linha = document.querySelector('#fPP\\:processosTable\\:tb tr.rich-table-row td:nth-child(2) a');
                return linha ? (linha.getAttribute('title') || linha.innerText.trim()) : null;
            });
        };

        const esperarMudancaPagina = async (paginaAntes, primeiroNumeroAntes, timeoutMs = 20000) => {
            const inicio = Date.now();
            while (Date.now() - inicio < timeoutMs) {
                const paginaAtualFooter = await getPaginaAtual();
                if (paginaAtualFooter && paginaAtualFooter !== paginaAntes) {
                    return paginaAtualFooter;
                }

                if (primeiroNumeroAntes) {
                    const primeiroAtual = await getPrimeiroNumeroTabela();
                    if (primeiroAtual && primeiroAtual !== primeiroNumeroAntes) {
                        return paginaAtualFooter || paginaAntes;
                    }
                }

                await delay(300);
            }
            return null;
        };

        // Navegar clicando em páginas visíveis (avança de 10 em 10)
        const irParaPaginaVisivel = async (numeroPagina, tentativas = 3) => {
            for (let tentativa = 0; tentativa < tentativas; tentativa++) {
                // Aguardar um pouco antes de tentar clicar
                await delay(300);

                const clicou = await iframe.evaluate((num) => {
                    const botoes = document.querySelectorAll('tfoot td');
                    for (const botao of botoes) {
                        const texto = botao.innerText.trim();
                        const ehAtivo = botao.className.includes('rich-datascr-act');
                        if (texto === num.toString() && !ehAtivo) {
                            // Verificar se o botão está desabilitado
                            if (botao.className.includes('dsbld')) {
                                return false;
                            }
                            botao.click();
                            return true;
                        }
                    }
                    return false;
                }, numeroPagina);

                if (clicou) {
                    return true;
                }

                await delay(500);
            }
            return false;
        };

        const getPaginasVisiveis = async () => {
            return await iframe.evaluate(() => {
                const paginas = [];
                document.querySelectorAll('tfoot td').forEach(td => {
                    const texto = td.innerText.trim();
                    const num = parseInt(texto);
                    if (!isNaN(num) && num > 0) {
                        paginas.push(num);
                    }
                });
                return paginas.sort((a, b) => a - b);
            });
        };

        const clicarControleNavegacao = async (chaves) => {
            return await iframe.evaluate((identificadores) => {
                const botoes = document.querySelectorAll('tfoot td.rich-datascr-button');
                for (const botao of botoes) {
                    const onclick = botao.getAttribute('onclick') || '';
                    if (botao.className.includes('dsbld')) continue;
                    if (identificadores.some(chave => onclick.includes(chave))) {
                        botao.click();
                        return true;
                    }
                }
                return false;
            }, chaves);
        };

        const clicarFastforward = async () => {
            return clicarControleNavegacao(["'page': 'fastforward'"]);
        };

        const avancarParaPagina = async (paginaDestino) => {
            if (!paginaDestino) return false;
            console.log(`⏭️  Retomando da página ${paginaDestino}...`);
            const maxIteracoes = 800;
            for (let i = 0; i < maxIteracoes; i++) {
                const atual = await getPaginaAtual();
                if (!atual) break;
                if (atual >= paginaDestino) {
                    console.log(`   ✓ Agora na página ${atual}`);
                    return true;
                }

                const paginasVisiveis = await getPaginasVisiveis();
                if (!paginasVisiveis.length) break;
                const maiorVisivel = Math.max(...paginasVisiveis);
                const alvoVisivel = paginaDestino <= maiorVisivel ? paginaDestino : maiorVisivel;
                const primeiroNumeroAntes = await getPrimeiroNumeroTabela();

                if (paginaDestino > maiorVisivel) {
                    if (!await clicarFastforward()) {
                        console.log('   ⚠️  Fastforward indisponível ao retomar');
                        return false;
                    }
                } else {
                    if (!await irParaPaginaVisivel(alvoVisivel)) {
                        console.log(`   ⚠️  Não conseguiu ir para ${alvoVisivel} ao retomar`);
                        return false;
                    }
                }

                const nova = await esperarMudancaPagina(atual, primeiroNumeroAntes);
                if (!nova || nova === atual) {
                    await delay(300);
                }
            }
            console.log('   ⚠️  Não conseguiu atingir a página alvo');
            return false;
        };

        const recarregarResultados = async (paginaDestino) => {
            console.log('   🔄 Recarregando consulta para sincronizar...');
            await executarBusca();
            if (paginaDestino) {
                await avancarParaPagina(paginaDestino);
            }
        };

        console.log('📚 Coletando TUDO...\n');
        
        let paginaAtual = await getPaginaAtual() || 1;
        let paginasSemNovos = 0;
        let travadoSeguido = 0;
        const limiteTravadoParaRefresh = 3;
        const limiteTravadoMaximo = 15;
        
        const deveRetomarPeloProgresso = !filtroDataAutuacaoFim;
        const paginaRetomar = deveRetomarPeloProgresso ? Math.max(1, Math.floor(todosProcessos.length / 20) + 1) : 1;
        if (deveRetomarPeloProgresso && paginaRetomar > paginaAtual) {
            await avancarParaPagina(paginaRetomar);
            paginaAtual = await getPaginaAtual() || paginaRetomar;
        }
        
        while (true) {
            console.log(`📄 Página ${paginaAtual}...`);
            
            const processos = await extrairProcessos();
            console.log(`   ${processos.length} processos`);
            
            let novos = 0;
            processos.forEach(p => {
                if (!numerosProcessosVistos.has(p.numero)) {
                    numerosProcessosVistos.add(p.numero);
                    todosProcessos.push(p);
                    novos++;
                }
            });
            
            if (novos === 0 && processos.length > 0) {
                paginasSemNovos++;
                console.log(`   ⚠️  Duplicados! (${paginasSemNovos})`);
            } else if (novos > 0) {
                paginasSemNovos = 0;
                console.log(`   ➕ ${novos} novos → ${todosProcessos.length} total`);
            }
            
            fs.writeFileSync(arquivoSaida, JSON.stringify(todosProcessos, null, 2));

            if (paginaAtual % 20 === 0 && paginaAtual > 0) {
                console.log(`\n🎯 ${paginaAtual} páginas | ${todosProcessos.length} processos`);
                console.log(`   🔄 Fechando aba e abrindo nova para limpar memória...\n`);

                // Fechar página atual
                await page.close().catch(() => {});

                // Criar nova página
                const newPage = await browser.newPage();
                await newPage.setViewport({ width: 1779, height: 1698 });
                newPage.setDefaultTimeout(15000);

                // Login novamente
                console.log('🔐 Login...');
                await newPage.goto('https://tjrj.pje.jus.br/pje/loginOld.seam', {
                    waitUntil: 'domcontentloaded',
                    timeout: 30000
                });
                await newPage.waitForSelector('#username');
                await newPage.type('#username', '48561184809', { delay: 30 });
                await newPage.type('#password', 'Julho3007!@', { delay: 30 });
                await Promise.all([
                    newPage.waitForNavigation({ waitUntil: 'domcontentloaded', timeout: 30000 }),
                    newPage.click('#btnEntrar')
                ]);
                console.log('✅ Logado!\n');

                // Atualizar referência global da página
                page = newPage;

                // Recalcular filtros de data com processos atualizados
                const datasValidas = todosProcessos
                    .map(p => parseDataBR(p.dataAutuacao))
                    .filter(data => data);
                if (datasValidas.length) {
                    const maisAntiga = datasValidas.reduce((min, atual) => atual < min ? atual : min);
                    filtroDataAutuacaoFim = formatarDataBR(maisAntiga);
                    filtroDataAutuacaoInicio = '01/01/2000';
                    console.log(`📅 Filtro atualizado: ${filtroDataAutuacaoInicio} → ${filtroDataAutuacaoFim}\n`);
                }

                // Navegar para consulta e buscar
                await navegarParaConsulta();
                iframe = await atualizarIframe();
                await executarBusca({ permitirManual: false });

                // Resetar contador de página
                paginaAtual = await getPaginaAtual() || 1;
                travadoSeguido = 0;
                paginasSemNovos = 0;
                continue;
            }

            // Estratégia: pular para a maior página visível
            const primeiroNumeroAntes = await getPrimeiroNumeroTabela();
            const paginasVisiveis = await getPaginasVisiveis();
            if (!paginasVisiveis.length) {
                console.log('   ⚠️  Não encontrou paginação. Saindo...');
                break;
            }
            const maiorVisivel = Math.max(...paginasVisiveis);
            
            console.log(`   Páginas visíveis: ${paginasVisiveis.join(', ')}`);
            
            // Se já estamos na maior visível, clicar em fastforward
            if (paginaAtual >= maiorVisivel) {
                console.log(`   ⏩ Tentando fastforward...`);
                
                if (!await clicarFastforward()) {
                    console.log(`\n✅ Fastforward indisponível - FIM\n`);
                    break;
                }
            } else {
                // Pular para a maior página visível
                const proximaPagina = paginaAtual + 1;
                const paginaAlvo = paginasVisiveis.includes(proximaPagina) ? proximaPagina : maiorVisivel;

                console.log(`   → Indo para página ${paginaAlvo}...`);

                if (!await irParaPaginaVisivel(paginaAlvo)) {
                    console.log(`   ⚠️  Não conseguiu clicar em ${paginaAlvo}, tentando fastforward...`);
                    if (!await clicarFastforward()) {
                        console.log(`   ⚠️  Fastforward também falhou`);
                        break;
                    }
                }
            }

            const novaPagina = await esperarMudancaPagina(paginaAtual, primeiroNumeroAntes);
            if (!novaPagina || novaPagina === paginaAtual) {
                travadoSeguido++;
                console.log(`   ⚠️  Travado em ${paginaAtual} (${travadoSeguido}/${limiteTravadoMaximo})`);
                if (travadoSeguido % limiteTravadoParaRefresh === 0) {
                    await recarregarResultados(paginaAtual + 1);
                    paginaAtual = await getPaginaAtual() || paginaAtual;
                    paginasSemNovos = 0;
                    travadoSeguido = 0;
                    continue;
                }
                if (travadoSeguido >= limiteTravadoMaximo) {
                    console.log(`\n❌ Travou ${limiteTravadoMaximo} vezes consecutivas - FIM\n`);
                    break;
                }
            } else {
                travadoSeguido = 0;
                console.log(`   ✓ ${paginaAtual} → ${novaPagina}\n`);
                paginaAtual = novaPagina;
            }
        }

        console.log('='.repeat(60));
        console.log('🎉 CONCLUÍDO!');
        console.log('='.repeat(60));
        console.log(`📊 ${todosProcessos.length} processos únicos`);
        console.log(`💾 ${arquivoSaida}`);
        console.log('='.repeat(60));
        
    } catch (error) {
        console.error('❌', error.message);
    } finally {
        await browser.close();
    }

})().catch(err => {
    console.error(err);
    process.exit(1);
});
