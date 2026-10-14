file="$HOME/experiment/out/report.rtf"
if [ -f "$file" ] && textutil -convert txt -stdout "$file" 2>/dev/null | grep -q 'Route comparison report'; then
    printf '{"passed":true,"detail":"report.rtf contains the text"}\n'
else
    printf '{"passed":false,"detail":"report.rtf missing or without the text"}\n'
fi
