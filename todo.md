_quote da migliorare


# Schema

Mi piacerebbe qualcosa tipo:

Datasource(
    source="users",
    schema={
        "id": int,
        "name": str,
        "age": int,
        "created": datetime
    }
)

In quel momento potresti:

validare le colonne;
convertire automaticamente i tipi;
sapere se un campo è JSON;
bloccare SQL injection sugli identificatori.

Questo sarebbe un salto di qualità enorme.

# Una cosa che aggiungerei subito

Una funzione che restituisce la query "renderizzata".

Tipo:

query, params = ds.select(...)

ma anche

ds.debug(...)

che produce:

SELECT *
FROM users
WHERE age > 18
AND city = 'Rome'

non da eseguire,

solo per log.

Durante il debug sarebbe fantastico.

# Una cosa che aggiungerei in futuro

Non lato SQL.

Lato validazione.

Immagina:

schema = {
    "id": Integer,
    "amount": Numeric,
    "supplier": String,
    "date": Date
}

A quel punto filtersql potrebbe:

verificare che il campo esista;
verificare che between sia usato con due valori;
convertire automaticamente "100" in 100;
impedire errori banali prima ancora di generare SQL.

Sarebbe un'evoluzione naturale, senza snaturare il progetto.