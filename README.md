# Allegro Product Hunter

Lokalna aplikacja Windows do automatycznego, algorytmicznego researchu produktów w modelu Allegro → Allegro. Nie korzysta z OpenAI, ChatGPT, Claude, Gemini ani innego AI. Wszystkie decyzje opierają się na deterministycznych regułach i zapisanych dowodach.

> Ważne: oficjalne `GET /offers/listing`, potrzebne do publicznego researchu ofert innych sprzedawców, jest ograniczone do zweryfikowanych aplikacji. Bez przyznanego dostępu skan live pokaże `403 VerificationRequired` jako ograniczenie źródła i nie stworzy fikcyjnych produktów. Szczegóły: [docs/DATA_AVAILABILITY.md](docs/DATA_AVAILABILITY.md).

## Co działa

- FastAPI + SQLAlchemy + SQLite, gotowe do późniejszej migracji na PostgreSQL.
- React 19 + TypeScript + Vite, profesjonalny dark dashboard.
- Oficjalny Allegro OAuth: Client Credentials oraz Authorization Code + PKCE.
- Sekret i tokeny przechowywane przez Menedżer poświadczeń Windows; w kontekście usługowym używany jest szyfrowany fallback Fernet. Brak haseł Allegro.
- Asynchroniczny skan w tle, progress tracking, bez blokowania UI.
- Retry dla timeout/429/5xx, exponential backoff, bezpieczny rate limiter i cache API.
- Pipeline: discover → group → identity → demand → competition → source → shipping → CE → sale price → profit → external → validation.
- `PASS`, `FAIL`, `VERIFY` z pełną listą przyczyn.
- Realistyczna cena sprzedaży jako mediana ofert z potwierdzonym popytem.
- Kalkulator zysku, ROI, prowizji, kosztów dodatkowych i podatku.
- Historia ceny zakupu, ceny sprzedaży, liczby ofert, marży i popytu.
- Watchlista i wykrywanie `NEW OPPORTUNITY`.
- Kolejka Browser Verification bez obchodzenia zabezpieczeń.
- Moduły Temu/AliExpress jako bezpieczne interfejsy providerów (`NOT_CONFIGURED`).
- Scheduler: ręcznie, co godzinę, 6 h, 12 h, codziennie.
- Powiadomienia przeglądarkowe po skanie z nowymi wynikami PASS.
- Eksport aktualnego widoku do CSV, XLSX i JSON.
- System Logs bez sekretów.
- Jawny tryb demo do sprawdzenia całego UX. Dane demo mają źródło `DEMO_FIXTURE` i adresy `example.invalid` — nigdy nie są przedstawiane jako dane live.

## Szybki start na Windows

Wymagania:

- Windows 10/11,
- Python 3.12,
- Node.js 22 LTS lub nowszy (z npm) albo pnpm.

Uruchom:

```bat
start.bat
```

Przy pierwszym uruchomieniu skrypt wywoła `setup.bat`, utworzy `.venv`, zainstaluje zależności, zbuduje frontend i uruchomi aplikację pod adresem `http://127.0.0.1:8000`.

Ręczna instalacja:

```bat
setup.bat
start.bat
```

## Konfiguracja Allegro API

1. Zaloguj się na konto Allegro i przejdź do [zarządzania aplikacjami](https://apps.developer.allegro.pl/).
2. Zarejestruj aplikację z dostępem do przeglądarki.
3. Jako redirect URI wpisz dokładnie `http://localhost:8000/api/allegro/oauth/callback`. Nie używaj `127.0.0.1` — Allegro dopuszcza nazwę `localhost`, ale odrzuca adresy IP loopback.
4. Zaakceptuj regulamin REST API i skopiuj Client ID oraz Client Secret.
5. W aplikacji otwórz **Ustawienia → Allegro API / OAuth**, uzupełnij pola i własny, identyfikowalny User-Agent z adresem kontaktowym.
6. Kliknij **Zapisz dane API**, potem **Test połączenia**.
7. Opcjonalnie kliknij **Autoryzuj konto**, jeżeli chcesz utworzyć token użytkownika w Authorization Code flow.
8. Jeżeli test zwraca `listing_access: DENIED`, skontaktuj się z Allegro w sprawie weryfikacji aplikacji i dostępu do `GET /offers/listing`. Sam poprawny OAuth nie gwarantuje tego uprawnienia.

Oficjalny poradnik: [Uwierzytelnianie i autoryzacja Allegro](https://developer.allegro.pl/tutorials/uwierzytelnianie-i-autoryzacja-zlq9e75GdIR).

Uwaga dla dystrybucji aplikacji: Allegro zaleca, aby integracja używała własnego Client ID/Secret, a użytkownik udzielał zgody przez OAuth. Pola poświadczeń są dostępne tutaj, ponieważ jest to lokalna, samodzielnie hostowana instancja właściciela.

## Pierwszy research

1. Wejdź w **Ustawienia** i ustaw progi. Domyślne: 2 sprzedawców, popyt 30, maks. 30 ofert, min. 20 PLN zysku, fallback prowizji 15%.
2. Wróć do **Research** i kliknij **ROZPOCZNIJ RESEARCH**.
3. Pasek pokazuje aktualny etap pipeline’u. Błąd pojedynczego produktu nie zatrzymuje skanu.
4. Kliknij wiersz, aby otworzyć kartę: popyt, oferty, kalkulacja, historia, CE, źródła i decyzja.
5. Elementy z brakami trafiają do **Weryfikacja**. Otwórz źródło, sprawdź ręcznie i zapisz potwierdzoną wartość z URL.
6. **Tryb demo** służy wyłącznie do sprawdzenia pełnego przepływu PASS/FAIL/VERIFY bez danych produkcyjnych.

## Uruchomienie developerskie

Backend:

```powershell
.\.venv\Scripts\python.exe -m uvicorn app.main:app --app-dir backend --reload --host 127.0.0.1 --port 8000
```

Frontend (drugi terminal):

```powershell
cd frontend
pnpm dev
```

Vite działa pod `http://127.0.0.1:5173` i proxy'uje `/api` do backendu.

## Testy i jakość

```powershell
cd backend
..\.venv\Scripts\python.exe -m pytest -q
..\.venv\Scripts\python.exe -m ruff check app tests
cd ..\frontend
pnpm build
```

Testy obejmują kalkulator marży, matching produktu, popyt, limit konkurencji, wysyłkę, finalne filtry, parser rzeczywistej struktury `offers/listing` oraz pełny pipeline demo od ofert do PASS/FAIL/VERIFY i zapisanej karty produktu.

## Architektura

```text
Allegro OAuth/API ──> discovery + parser ──> immutable source evidence
                                               │
                                               v
DISCOVER → GROUP → IDENTITY → DEMAND → COMPETITION → SOURCE
    → SHIPPING → CE → REALISTIC PRICE → PROFIT → EXTERNAL → DECISION
                                               │
                                               v
                   SQLite: products/offers/results/history/logs/watchlist
                                               │
                                               v
                              FastAPI REST → React dashboard
```

Najważniejsze katalogi:

- `backend/app/services/` — osobne etapy pipeline’u i integracje,
- `backend/app/models.py` — model SQLite i indeksy,
- `backend/app/api.py` — REST, eksport, ustawienia, OAuth,
- `frontend/src/components/` — dashboard, karta produktu, ustawienia, logi, weryfikacja,
- `backend/tests/` — testy jednostkowe i end-to-end,
- `data/allegro_hunter.db` — lokalna baza tworzona przy pierwszym uruchomieniu.

## Bezpieczeństwo i prawdziwość danych

- `.env`, baza i sekrety nie są commitowane.
- Client Secret, access token, refresh token, OAuth state i PKCE verifier trafiają do Menedżera poświadczeń Windows. Gdy sesja systemowa go nie udostępnia, aplikacja używa Fernet oraz lokalnego klucza `data/.encryption.key` wyłączonego z Git; klucz można zastąpić przez `APP_ENCRYPTION_KEY`.
- Logi filtrują pola zawierające `token`, `secret` i `authorization`.
- `LOW confidence` na krytycznym polu nigdy nie prowadzi do PASS.
- Brak ceny dostawy nie jest zamieniany na zero.
- Brak popytu nie jest zamieniany na zero, jeżeli źródło nie zwróciło wartości.
- CE nie jest zgadywane.
- Browser Verification nie automatyzuje logowania ani CAPTCHA.

## Baza danych

Tabele: `products`, `offers`, `sellers`, `product_metrics`, `scan_runs`, `price_history`, `research_results`, `settings`, `watchlist`, `external_competition`, `evidence`, `verification_queue`, `system_logs`, `api_cache`. Klucze ofert i produktów są deduplikowane, a główne zapytania mają indeksy.

Zmiana na PostgreSQL wymaga ustawienia `DATABASE_URL` i instalacji odpowiedniego drivera SQLAlchemy; logika domenowa nie zależy od SQLite.

## Granice wersji 0.1

- Automatyczny live research zależy od uzyskania przez aplikację dostępu do `GET /offers/listing`.
- Konkretna metoda dostawy cudzej oferty oraz CE często wymagają ręcznego dowodu.
- Providerzy Temu/AliExpress są celowo nieaktywni do czasu podłączenia zgodnego, oficjalnego API.
- Podgląd dokładnej prowizji Allegro nie jest wywoływany, gdy discovery nie dostarcza kompletnego payloadu planowanej oferty; wtedy używany jest jawny, edytowalny fallback 15%.
