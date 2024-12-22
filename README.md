# Proiect PR IoT: Sistem de casa inteligent pentru controlul intensitatii luminii dintr-o incapere

## Structura retelei in linii mari

Datele de la senzorul de lumina sunt preluate si prelucrate cu ajutorul unui microcontroller de tip ESP32, programat pentru simplitate in MicroPython. Acestea
sunt trimise pe cale wireless catre serverul central (care ruleaza pe laptop-ul personal) ce expune o interfata web utilizatorului pentru a vizualiza
datele despre intensitatea luminii si a lua decizii asupra actuatorului (pornire/oprire, setare luminozitate, determinarea parametrilor acestuia, aplicarea
modului twinkle). Actuatorul (un bec inteligent) este si el controlat la randul lui prin intermediul Wi-Fi. Toate aceste componente sunt conectate la aceeasi
retea pentru a asigura buna functionare, fiind necesare informatiile despre aceasta (SSID si parola pentru conectare). In afara de aceste detalii este nevoie
si de aflarea IP-ului si token-ului unic (stabilit la inregistrarea dispozitivului) asociat becului de tip Mi Smart LED, conform documentatiei [de aici](https://github.com/Squachen/micloud/).

## Preluarea datelor de la senzor si transmiterea lor catre server

Inainte de stabilirea conexiunii si transmiterea efectiva a datelor se determina urmatoarele constante:
- SSID-ul router-ului de Wi-Fi din reteaua locala;
- parola retelei;
- date despre server-ul ce ruleaza pe laptopul personal;
- adresa IP (aflata in timpul rularii);
- portul pe care ruleaza (fixat la runtime);
- URL-ul la care se trimit datele, de forma `http://{SERVER_IP}:{SERVER_PORT}/<calea_operatiei_de_primire_a_datelor_definita_in_cadrul_serverului>`.

Logica programului este urmatoarea:
1. se realizeaza conexiunea microcontroller-ului la reteaua Wi-Fi locala;
2. se seteaza pinul GPIO la care este conectat fotorezistorul (in acest caz pinul logic corespunde celui fizic denumit VN);
3. se seteaza atenuarea valorilor citite cu ajutorul ADC-ului corespunzatoare tensiunii circuitului (in acest caz 6 dB);
4. intr-o bucla infinita se citeste valoarea curenta de la senzor (care este normalizata pentru a fi in intervalul 0-100, precum luminozitatea becului), se construieste payload-ul ce o contine (obiect JSON), se trimite catre server si se asteapta 1 minut intre citiri.

## Constructia serverului
Modalitatea aleasa de realizare a serverului este cea reprezentata de utilizarea framework-ului Flask, intrucat se integreaza facil baza de date SQLite3 si functionalitatea se redacteaza in mod intuitiv, cu ajutorul rutelor. Fiecare ruta defineste cate o operatie expusa de interfata web construita cu ajutorul template-urilor HTML:
- `/` -> pagina principala a aplicatiei, care expune butoane pentru alegerea actiunii de catre utilizator;
- `/login` -> introducerea IP-ului si token-ului aferente becului (nu se poate trece la pagina de pornire fara acestea); optional, pentru a putea emite statisticile calculate pe telefon, se pot introduce token-ul asociat bot-ului custom Telegram configurat in prealabil si ID-ul chat-ului pe care se vor primi mesajele;
- `/turn-on` -> se trimite comanda de pornire a becului;
- `/turn-off` -> se trimite comanda de stingere a becului;
- `/set-brightness` -> se trimite comanda de actualizare a luminozitatii becului conform valorii introduse de utilizator in pagina;
- `/adjust-brightness` -> se trimite comanda de actualizare a luminozitatii becului conform ultimei valori citite de la senzor;
- `/current-status` -> se trimite comanda de determinare a starii curente a becului (daca este pornit/oprit si procentul de luminozitate);
- `/visualizeData` -> se construieste graficul intensitatii luminoase din incapere, al statusului becului si a gradului de luminozitate a becului in functie de timp, care se actualizeaza in timp real pe masura ce senzorul citeste datele si sunt introduse in baza de date;
- `/getStatistics` -> se determina statistici relevante pe baza datelor aflate la un moment dat in baza de date (media valorilor intensitatilor luminoase preluate de la senzor si cele unice inregistrate); de asemenea, pentru simplitate, se estimeaza urmatoarea valoare a intensitatii cu ajutorul metodei ARIMA; aceste informatii sunt trimise utilizatorului pe telefon prin intermediul aplicatiei Telegram, pentru a tine evidenta gradului de lumina din incapere mai usor de la distanta;
- `/twinkle` -> se trimite comanda de creare a unui efect luminos pentru bec: clipire de 3 ori.

Pentru afisarea graficului s-a folosit framework-ul Chart.js, intrucat este usor de incorporat in template-ul HTML. Valorile introduse in grafic sunt preluate direct din baza de date cu ajutorul rutei `/getDBData` (ce aplica un query de SELECT asupra tabelei). Microcontroller-ul trimite cereri de tip POST serverului la ruta `/submit` ce contin valorile intensitatii luminoase; payload-ul este extras si introdus in baza de date alaturi de data la care au ajuns cererile, starea becului, luminozitatea lui curenta si temperatura culorii. Graficul rezultat se actualizeaza in timp real, o data la 5 secunde, pentru a putea observa facil modificarile gradului de lumina din incapere si efectul adaptarii automate a luminozitatii actuatorului. Rezultatul in urma operatiilor de actualizare a valorii luminozitatii actuatorului este afisat la ruta `/set-brightness-result/<bright>/<err>/<res>`, in urma redirectarii de la `/set-brightness` care transmite prin query params valoarea noua a luminozitatii, daca operatia a fost efectuata cu succes si mesajul care se afisează in pagina.

## Structura repository-ului

- `/server` -> contine toate fisierele necesare rularii serverului Flask pe laptop-ul personal;
- `server/main.py` -> contine toata logica necesara definirii rutelor serverului, instantierii bazei de date si a primirii datelor de la microcontroller; **acesta este script-ul care se ruleaza pentru a pune in functiune serverul**;
- `/server/templates` -> contine scheletele HTML asociate paginilor web si a rutelor definite pentru server;
- `/server/schema.py` -> defineste structura bazei de date in care sunt introduse valorile citite de catre microcontroller;
- `esp32.py` -> contine script-ul de MicroPython ce se urca pe microcontroller-ul de tip ESP32 pentru citirea datelor de la senzor si trimiterea lor la server pentru a fi stocate in baza de date.

## Prequisites (de instalare)
Comenzile catre actuator sunt trimise cu ajutorul package-ului Python [de aici](https://github.com/rytilahti/python-miio), care trebuie instalat in prealabil alaturi de [Flask](https://pypi.org/project/Flask/) cu parametrul `[async]` si de pachetul necesar modelului ARIMA de estimare a urmatoarei valori a intensitatii luminoase din incapere: [statsmodel](https://www.statsmodels.org/dev/install.html) pe laptop-ul personal.
