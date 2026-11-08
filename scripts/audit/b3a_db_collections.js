const r = [];
db.getCollectionNames().sort().forEach(c => {
  r.push(c + "\t" + db.getCollection(c).estimatedDocumentCount());
});
print(r.join("\n"));
print("TOTAL\t" + r.length);
