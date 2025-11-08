#!/bin/bash
# Script para rodar importação dos 51k processos TJRJ PJE

echo "================================================================"
echo "IMPORTAÇÃO DE PROCESSOS TJRJ PJE AUTENTICADO"
echo "================================================================"
echo ""
echo "🚀 Iniciando importação com 20 requisições paralelas..."
echo ""
echo "📊 Para acompanhar o progresso em tempo real, abra outro terminal e execute:"
echo ""
echo "    docker exec stack-api tail -f /tmp/import_tjrj_progress.log"
echo ""
echo "================================================================"
echo ""

# Rodar importação em background
docker exec -w /app stack-api python3 scripts/import_tjrj_pje_auth.py --parallel 20 &
IMPORT_PID=$!

# Aguardar um pouco e começar a mostrar o log
sleep 5
echo "📈 Mostrando progresso (Ctrl+C para parar de ver, mas importação continua):"
echo ""
docker exec stack-api tail -f /tmp/import_tjrj_progress.log

# Aguardar processo terminar
wait $IMPORT_PID

echo ""
echo "✅ Importação finalizada!"
echo ""
echo "Para ver o resumo final:"
echo "    docker exec stack-api tail -20 /tmp/import_tjrj_progress.log"
echo ""
