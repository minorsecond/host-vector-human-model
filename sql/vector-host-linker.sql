--CREATE INDEX host_gix ON public."Humans" USING GIST (geom);
--CREATE INDEX vector_gix ON Vectors USING GIST (geom);
DELETE FROM vector_human_links;

INSERT INTO vector_human_links (human_id, vector_id, distance)
SELECT h.id, v.id, ST_Distance(h.geom, v.geom)
	FROM public."Humans" h
	JOIN Vectors v on ST_DWithin(v.geom, h.geom, v.vector_range);