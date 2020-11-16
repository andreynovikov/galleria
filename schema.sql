CREATE TABLE author (
    id integer NOT NULL,
    name character varying(100) NOT NULL
);

CREATE SEQUENCE author_id_seq
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;

CREATE TABLE image (
    id integer NOT NULL,
    name character varying(250) DEFAULT ''::character varying NOT NULL,
    bundle character varying(250) DEFAULT ''::character varying NOT NULL,
    width integer DEFAULT 0 NOT NULL,
    height integer DEFAULT 0 NOT NULL,
    stime timestamp without time zone,
    description text,
    ctime timestamp without time zone,
    mtime timestamp without time zone,
    author integer,
    starred integer DEFAULT 0 NOT NULL,
    lat double precision,
    lon double precision,
    prefered boolean DEFAULT false NOT NULL,
    exportable boolean DEFAULT false NOT NULL,
    censored integer DEFAULT 0 NOT NULL
);

CREATE SEQUENCE image_id_seq
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;

CREATE TABLE label (
    id integer NOT NULL,
    name character varying(100) NOT NULL
);

CREATE SEQUENCE label_id_seq
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;

CREATE TABLE label_image (
    image integer NOT NULL,
    label integer NOT NULL
);

CREATE TABLE log (
    image integer NOT NULL,
    "user" character varying(60) NOT NULL,
    status integer NOT NULL,
    ctime timestamp without time zone DEFAULT now()
);

ALTER TABLE ONLY author ALTER COLUMN id SET DEFAULT nextval('author_id_seq'::regclass);

ALTER TABLE ONLY image ALTER COLUMN id SET DEFAULT nextval('image_id_seq'::regclass);

ALTER TABLE ONLY label ALTER COLUMN id SET DEFAULT nextval('label_id_seq'::regclass);

ALTER TABLE ONLY author
    ADD CONSTRAINT author_pkey PRIMARY KEY (id);

ALTER TABLE ONLY author
    ADD CONSTRAINT author_name_key UNIQUE (name);

ALTER TABLE ONLY image
    ADD CONSTRAINT image_pkey PRIMARY KEY (id);

ALTER TABLE ONLY label
    ADD CONSTRAINT label_pkey PRIMARY KEY (id);

ALTER TABLE ONLY label
    ADD CONSTRAINT label_name_key UNIQUE (name);

CREATE INDEX image_bundle ON image USING btree (bundle);

CREATE UNIQUE INDEX label_image_label_image ON label_image USING btree (label, image);

ALTER TABLE ONLY image
    ADD CONSTRAINT image_author_fkey FOREIGN KEY (author) REFERENCES author(id) ON DELETE RESTRICT;

ALTER TABLE ONLY label_image
    ADD CONSTRAINT label_image_image_fkey FOREIGN KEY (image) REFERENCES image(id) ON DELETE CASCADE;

ALTER TABLE ONLY label_image
    ADD CONSTRAINT label_image_label_fkey FOREIGN KEY (label) REFERENCES label(id) ON DELETE RESTRICT;

ALTER TABLE ONLY log
    ADD CONSTRAINT log_image_fkey FOREIGN KEY (image) REFERENCES image(id) ON DELETE CASCADE;
