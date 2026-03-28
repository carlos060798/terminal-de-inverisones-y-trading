from edgar import Company, set_identity
set_identity("QuantumTerminal Debugger (admin@quantumterminal.ai)")

company = Company("AAPL")
filing = company.get_filings(form="10-K").latest()
print(f"Tipo de objeto: {type(filing)}")
print(f"Atributos: {dir(filing)}")

try:
    obj = filing.obj()
    print(f"\nTipo de objeto .obj(): {type(obj)}")
    print(f"Atributos .obj(): {dir(obj)}")
except Exception as e:
    print(f"\nError al llamar .obj(): {e}")

try:
    xbrl = filing.xbrl()
    print(f"\nXBRL detectado: {xbrl is not None}")
    if xbrl:
        print(f"Atributos XBRL: {dir(xbrl)}")
except Exception as e:
    print(f"\nError al llamar .xbrl(): {e}")
