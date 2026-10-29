# Bourse des filles

Les portefeuilles de Juliette et d'Ines, publiés sur GitHub Pages :

- https://romano-devil.github.io/bourse-filles/juliette.html
- https://romano-devil.github.io/bourse-filles/ines.html

Les cours viennent de Yahoo Finance. Le workflow `mise-a-jour.yml` régénère les pages chaque soir de semaine.

Pour changer une date d'achat, un montant ou saisir le vrai prix payé, modifier `portefeuilles.json`
(le bloc `achat` d'une action : `prix`, `eurusd`, `nb_actions`) puis pousser sur `main`.
Pour tester en local : `python3 build.py`, puis ouvrir `site/juliette.html`.
