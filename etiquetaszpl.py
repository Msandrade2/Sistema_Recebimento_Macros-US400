import socket
import logging

IMPRESSORAS = {
    "BRTEMAN01": {
        "ip": "169.6.169.230",
        "margem_peq_med_gra": "30",
        "margem_outros": "25",
        "length_peq_med_gra": "190", 
        "length_outros": "180",
        "zpl": lambda endereco, length, margem, movimentacao, upin: f"""
            ^XA
            ^PRC
            ^FO500,30^BQ0N,4,4^FDQA,{endereco}^FS
            ^CF0,250
            ^FO{margem},135^A0N,450,{length}^FD{endereco}^FS
            ^CFC,25
            ^FO30,510^A0N,40,40^FDW{movimentacao}^FS
            ^FO500,520^FD{upin}^FS
            ^XZ
        """
    },
    "BRTEMAN02": {
        "ip": "169.6.169.208",
        "margem_peq_med_gra": "20", 
        "margem_outros": "20",
        "length_peq_med_gra": "140", 
        "length_outros": "130",
        "zpl": lambda endereco, length, margem, movimentacao, upin: f"""
            ^XA
            ^PRC
            ^FO350,25^BQ0N,3,3^FDQA,{endereco}^FS
            ^CF0,230
            ^FO{margem},110^A0N,350,{length}^FD{endereco}^FS
            ^CFC,25
            ^FO30,390^A0N,30,30^FDW{movimentacao}^FS
            ^FO350,390^FD{upin}^FS
            ^XZ
        """
    }
}

def imprimir_etiqueta(enderecos, zona="", movimentacao="", upin="", impressora="BRTEMAN01"):
    if not enderecos:
        return

    impressora_cfg = IMPRESSORAS.get(impressora)
    if not impressora_cfg:
        raise ValueError(f"Impressora '{impressora}' não reconhecida.")

    zona = zona.upper().strip()
    margem = impressora_cfg["margem_peq_med_gra"] if zona in ["PEQ", "MED", "GRA"] else impressora_cfg["margem_outros"]
    length = impressora_cfg["length_peq_med_gra"] if zona in ["PEQ", "MED", "GRA"] else impressora_cfg["length_outros"]
    ip = impressora_cfg["ip"]
    port = 9100
    gerar_zpl = impressora_cfg["zpl"]

    try:
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            s.settimeout(5)
            s.connect((ip, port))

            for endereco in enderecos:
                zpl = gerar_zpl(endereco, length, margem, movimentacao, upin)
                s.sendall(zpl.encode('ISO-8859-1'))

    except (socket.timeout, socket.error) as e:
        logging.error(f"[IMPRESSÃO] Falha ao conectar à impressora: {e}")
        raise ConnectionError("Erro ao conectar à impressora. Verifique se está ligada e acessível.")