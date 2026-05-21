
URL="http://127.0.0.1:18080/api/ecoflow/chat"
SESSION_ID="repro_$(date +%s)"

echo "Turn 1"
curl -s -X POST "$URL" -F "session_id=$SESSION_ID" -F "message=Da de alta una tarea para Maria, cliente Cristian, el viernes a las 12. Tarea: Instalar aire" | python3 -m json.tool
echo
echo "Turn 2"
curl -s -X POST "$URL" -F "session_id=$SESSION_ID" -F "message=3" | python3 -m json.tool
echo
echo "Turn 3"
curl -s -X POST "$URL" -F "session_id=$SESSION_ID" -F "message=5" | python3 -m json.tool
echo
echo "Turn 4 (CONFIRM)"
curl -s -X POST "$URL" -F "session_id=$SESSION_ID" -F "message=Si" | python3 -m json.tool
echo
