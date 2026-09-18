# Dostępność danych Allegro — stan na 17.09.2026

Projekt stosuje zasadę **evidence first**: wartość krytyczna bez źródła nie może prowadzić do `PASS`.

## Co udostępnia oficjalne API

| Dane | Oficjalne źródło | Uwagi aplikacji |
|---|---|---|
| Publiczna lista ofert, cena, sprzedawca, `sellingMode.popularity`, najniższy koszt dostawy | `GET /offers/listing` | Dostęp tylko dla zweryfikowanych aplikacji. Nowa aplikacja może otrzymać `403 VerificationRequired`. |
| Katalog produktów i parametry | `GET /sale/products`, `GET /sale/products/{productId}` | To nie jest lista aktywnych ofert konkurencji. |
| Własne oferty zalogowanego sprzedawcy | `GET /sale/offers`, `GET /sale/product-offers/{offerId}` | Nie daje pełnych danych ofert innych sprzedawców. |
| Lista globalnych metod dostawy | `GET /sale/delivery-methods` | Nie potwierdza przewoźnika przypisanego do konkretnej cudzej oferty. |
| Podgląd opłat | `POST /pricing/offer-fee-preview` | Wymaga danych planowanej oferty. Jeżeli brak kompletu parametrów, aplikacja stosuje jawny konserwatywny fallback 15%. |
| OAuth | Authorization Code, Device, Client Credentials | Aplikacja implementuje Authorization Code + PKCE i Client Credentials. |

## Czego aplikacja nie wywnioskuje

- Pole `popularity` jest zapisywane dokładnie jako wskaźnik Allegro; UI nie nazywa go arbitralnie liczbą sprzedaży.
- `GET /offers/listing` nie potwierdza Allegro Product ID/EAN ani konkretnego przewoźnika dla każdej pozycji. Grupowanie wyłącznie po tytule ma `LOW confidence` i wymusza `VERIFY`.
- CE nie jest wyznaczane na podstawie samej kategorii ani słów kluczowych. Brak dokumentu/parametru/wiarygodnego źródła daje `CE VERIFY`.
- Temu i AliExpress nie mają w projekcie skonfigurowanego oficjalnego providera. Moduły zwracają `NOT_CONFIGURED`, a architektura pozwala dodać legalny provider/API później.
- Browser Verification nie loguje się, nie rozwiązuje CAPTCHA, nie obchodzi ochrony antybotowej i nie omija limitów. Tworzy kolejkę z bezpośrednim linkiem oraz formularzem ręcznego dowodu.

## Konsekwencja dla statusu

`PASS` jest możliwy wyłącznie, gdy tożsamość, popyt, liczba ofert, źródło zakupu, koszt i metoda dostawy, CE (jeśli dotyczy), cena sprzedaży oraz kalkulacja kosztów mają dowody. Brak dowodu krytycznego daje `VERIFY`. Twarde przekroczenie progu daje `FAIL`.

Dokumentacja: [Allegro REST API](https://developer.allegro.pl/documentation), [OAuth](https://developer.allegro.pl/tutorials/uwierzytelnianie-i-autoryzacja-zlq9e75GdIR), [sprawdzanie opłat](https://developer.allegro.pl/tutorials/jak-sprawdzic-oplaty-nn9DOL5PASX).

