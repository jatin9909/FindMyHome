# FindMyHome
A recommendation system to recommend properties to the user using GraphDB.

## GraphDB Schema:
Node properties: <br>
Property {id: STRING, name: STRING, totalArea: FLOAT, pricePerSqft: FLOAT, price: FLOAT, beds: INTEGER, baths: INTEGER, hasBalcony: BOOLEAN, description: STRING} <br>
Neighborhood {name: STRING} <br>
City {name: STRING} <br>
PropertyType {name: STRING} <br>
RoomType {name: STRING, rooms: INTEGER} <br>

Relationship properties: <br>
The relationships: <br>
(:Property)-[:IN_NEIGHBORHOOD]->(:Neighborhood) <br>
(:Property)-[:OF_TYPE]->(:PropertyType) <br>
(:Property)-[:HAS_LAYOUT]->(:RoomType) <br>
(:Neighborhood)-[:PART_OF]->(:City) <br>


![Untitled Diagram (1).png](imgs%2FUntitled%20Diagram%20%281%29.png)