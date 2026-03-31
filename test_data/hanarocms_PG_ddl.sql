-- PostgreSQL DDL for HANAROCMS
-- Generated from hanarocms_oracle_ddl.sql

-- Schema creation
CREATE SCHEMA IF NOT EXISTS hanarocms;

-- 1. PHYSICAL_STB
CREATE TABLE hanarocms.physical_stb (
	idx NUMERIC(10,0) NOT NULL,
	serial_no VARCHAR(30) NOT NULL,
	mac_address VARCHAR(20) NOT NULL,
	produced_country VARCHAR(20),
	factory VARCHAR(20),
	model_code VARCHAR(10) NOT NULL,
	produced_date TIMESTAMP,
	status_code SMALLINT,
	flag CHAR(1),
	stb_id CHAR(38),
	managed_no VARCHAR(22),
	user_service_num VARCHAR(12),
	mfact_ser_num VARCHAR(40),
	pdi VARCHAR(64),
	CONSTRAINT pk_physical_stb PRIMARY KEY (mac_address)
);

CREATE INDEX ix_physical_stb_2b ON hanarocms.physical_stb (stb_id);
CREATE INDEX physical_stb_idx3 ON hanarocms.physical_stb (mfact_ser_num);
CREATE INDEX physical_stb_idx4 ON hanarocms.physical_stb (model_code, stb_id);
CREATE INDEX xie1physical_stbb ON hanarocms.physical_stb (user_service_num);

-- 2. STB
CREATE TABLE hanarocms.stb (
	stb_id CHAR(38) NOT NULL,
	user_num VARCHAR(12) NOT NULL,
	user_service_num VARCHAR(12) NOT NULL,
	user_init_num VARCHAR(12) NOT NULL,
	subscription_type CHAR(1),
	subscribed_service CHAR(1),
	adult_pw VARCHAR(4) DEFAULT '1111',
	free_space NUMERIC(10,0),
	installation_id CHAR(38),
	internet_info_id CHAR(38),
	sw_version VARCHAR(20),
	epg_version NUMERIC(10,0),
	payment_info_id CHAR(38),
	network_info_id CHAR(38),
	flag_lock CHAR(1),
	flag_install_required CHAR(1),
	flag_lease VARCHAR(20),
	agent_id CHAR(38),
	recommender_id VARCHAR(14),
	recommender_company VARCHAR(30),
	id_biz SMALLINT,
	quality_type CHAR(2),
	service_status_code SMALLINT,
	stb_usage_code SMALLINT,
	pin_no VARCHAR(50),
	service_code SMALLINT,
	user_id VARCHAR(50),
	network_brand_code SMALLINT,
	id_package NUMERIC(10,0),
	kid_pw VARCHAR(4) DEFAULT '1111',
	unlock_time TIMESTAMP DEFAULT '2999-12-31 00:00:00'::TIMESTAMP,
	purchase_pw VARCHAR(4) DEFAULT '1111',
	tv_package SMALLINT,
	iptv_status_code SMALLINT,
	network_type SMALLINT,
	iptv_usable SMALLINT,
	iptv_type VARCHAR(5),
	pd_package SMALLINT,
	tech_mthd_cd VARCHAR(5),
	fee_prod_cd VARCHAR(10),
	cust_typ_cd VARCHAR(3),
	enc_adult_pin VARCHAR(80) DEFAULT '0ffe1abd1a08215353c233d6e009613e95eec4253832a761af28ff37ac5a150c',
	enc_kid_pin VARCHAR(80) DEFAULT '0ffe1abd1a08215353c233d6e009613e95eec4253832a761af28ff37ac5a150c',
	enc_purchase_pin VARCHAR(80) DEFAULT '0ffe1abd1a08215353c233d6e009613e95eec4253832a761af28ff37ac5a150c',
	CONSTRAINT pk_stb PRIMARY KEY (stb_id)
);

CREATE INDEX ix_stbb ON hanarocms.stb (user_init_num, stb_id, user_num, user_service_num);
CREATE UNIQUE INDEX ix_stb_service_code ON hanarocms.stb (service_code, stb_id);
CREATE INDEX ix_stb_user_service_numb ON hanarocms.stb (user_service_num);
CREATE INDEX xie1stbb ON hanarocms.stb (user_num);

-- 3. STB_DTL
CREATE TABLE hanarocms.stb_dtl (
	stb_id CHAR(38) NOT NULL,
	user_service_num VARCHAR(12) NOT NULL,
	srel_int_svc_tech_mthd_cd VARCHAR(5),
	srel_int_svc_mgmt_num VARCHAR(10),
	use_infoagr_yn VARCHAR(1),
	use_infoagr_dt_insert TIMESTAMP,
	use_infoagr_dt_update TIMESTAMP,
	tbr_cust_id VARCHAR(10),
	tbr_sspt_id VARCHAR(10),
	wtr_mark_id VARCHAR(9),
	stb_nnm VARCHAR(30),
	swing_user_num VARCHAR(12),
	swing_user_service_num VARCHAR(12),
	tbr_so_cl_cd VARCHAR(4),
	tbr_so_cnvt_dtm TIMESTAMP,
	scrbr_typ_cd VARCHAR(2) DEFAULT '1',
	bf_term_user_service_num VARCHAR(12),
	pai VARCHAR(38),
	ai_agree_yn VARCHAR(1),
	CONSTRAINT pk_stb_dtl PRIMARY KEY (stb_id)
);

CREATE UNIQUE INDEX idx_stb_dtl_1 ON hanarocms.stb_dtl (user_service_num);
CREATE UNIQUE INDEX idx_stb_dtl_2 ON hanarocms.stb_dtl (swing_user_service_num);

-- 4. STB_LOCATION
CREATE TABLE hanarocms.stb_location (
	stb_id CHAR(38) NOT NULL,
	user_num VARCHAR(12) NOT NULL,
	user_service_num VARCHAR(12) NOT NULL,
	user_init_num VARCHAR(12) NOT NULL,
	post_no VARCHAR(7),
	address VARCHAR(170),
	phone VARCHAR(20),
	cel_phone VARCHAR(20),
	addr_id VARCHAR(15),
	mgmt_ord_id VARCHAR(10),
	post_org_id VARCHAR(10),
	new_post_no VARCHAR(6),
	CONSTRAINT pk_stb_location PRIMARY KEY (stb_id)
);

CREATE INDEX xie1stb_locationb ON hanarocms.stb_location (post_no);
CREATE INDEX xie2stb_locationb ON hanarocms.stb_location (user_init_num);
CREATE INDEX xie3stb_locationb ON hanarocms.stb_location (user_num);
CREATE INDEX xie4stb_locationb ON hanarocms.stb_location (user_service_num);

-- 5. STB_MODEL
CREATE TABLE hanarocms.stb_model (
	model_code VARCHAR(10) NOT NULL,
	model_name VARCHAR(20),
	model_desc VARCHAR(20),
	pdi_secret_key VARCHAR(50) NOT NULL,
	CONSTRAINT pk_stb_model PRIMARY KEY (model_code)
);

-- 6. TOAD_PLAN_TABLE
CREATE TABLE hanarocms.toad_plan_table (
	statement_id VARCHAR(30),
	plan_id NUMERIC,
	timestamp TIMESTAMP,
	remarks VARCHAR(4000),
	operation VARCHAR(30),
	options VARCHAR(255),
	object_node VARCHAR(128),
	object_owner VARCHAR(30),
	object_name VARCHAR(30),
	object_alias VARCHAR(65),
	object_instance NUMERIC(38,0),
	object_type VARCHAR(30),
	optimizer VARCHAR(255),
	search_columns NUMERIC,
	id NUMERIC(38,0),
	parent_id NUMERIC(38,0),
	depth NUMERIC(38,0),
	position NUMERIC(38,0),
	cost NUMERIC(38,0),
	cardinality NUMERIC(38,0),
	bytes NUMERIC(38,0),
	other_tag VARCHAR(255),
	partition_start VARCHAR(255),
	partition_stop VARCHAR(255),
	partition_id NUMERIC(38,0),
	other TEXT,
	distribution VARCHAR(30),
	cpu_cost NUMERIC(38,0),
	io_cost NUMERIC(38,0),
	temp_space NUMERIC(38,0),
	access_predicates VARCHAR(4000),
	filter_predicates VARCHAR(4000),
	projection VARCHAR(4000),
	time NUMERIC(38,0),
	qblock_name VARCHAR(30),
	other_xml TEXT
);

-- 7. ZNGM_ADDR
CREATE TABLE hanarocms.zngm_addr (
	addr_id VARCHAR(15) NOT NULL,
	audit_id VARCHAR(15) NOT NULL,
	audit_dtm TIMESTAMP NOT NULL,
	eff_sta_dt VARCHAR(8) NOT NULL,
	eff_end_dt VARCHAR(8) NOT NULL,
	ldong_cd VARCHAR(10) NOT NULL,
	house_num_typ_cd VARCHAR(1) NOT NULL,
	main_house_num_ctt VARCHAR(40) NOT NULL,
	sub_house_num_ctt VARCHAR(40) NOT NULL,
	bld_cd VARCHAR(15) NOT NULL,
	st_nm_cd VARCHAR(12),
	bld_main_num VARCHAR(10),
	bld_sub_num VARCHAR(10),
	CONSTRAINT pk_zngm_addr PRIMARY KEY (addr_id)
);

-- 8. ZNGM_LDONG
CREATE TABLE hanarocms.zngm_ldong (
	ldong_cd VARCHAR(10) NOT NULL,
	audit_id VARCHAR(15) NOT NULL,
	audit_dtm TIMESTAMP NOT NULL,
	eff_sta_dt VARCHAR(8) NOT NULL,
	eff_end_dt VARCHAR(8) NOT NULL,
	ldong_cl_cd VARCHAR(1) NOT NULL,
	ct_pvc_nm VARCHAR(20) NOT NULL,
	ct_gun_gu_nm VARCHAR(40),
	up_myun_dong_nm VARCHAR(100),
	ri_nm VARCHAR(20),
	sup_ldong_cd VARCHAR(10),
	CONSTRAINT pk_zngm_ldong PRIMARY KEY (ldong_cd)
);

-- 9. ZNGM_LRDONG_REL
CREATE TABLE hanarocms.zngm_lrdong_rel (
	ldong_cd VARCHAR(10) NOT NULL,
	rdong_cd VARCHAR(10) NOT NULL,
	eff_sta_dt VARCHAR(8) NOT NULL,
	eff_end_dt VARCHAR(8) NOT NULL,
	audit_id VARCHAR(15) NOT NULL,
	audit_dtm TIMESTAMP NOT NULL,
	CONSTRAINT pk_zngm_lrdong_rel PRIMARY KEY (ldong_cd, rdong_cd, eff_sta_dt, eff_end_dt)
);

-- 10. ZNGM_RDONG
CREATE TABLE hanarocms.zngm_rdong (
	rdong_cd VARCHAR(10) NOT NULL,
	audit_id VARCHAR(15) NOT NULL,
	audit_dtm TIMESTAMP NOT NULL,
	eff_sta_dt VARCHAR(8) NOT NULL,
	eff_end_dt VARCHAR(8) NOT NULL,
	ct_pvc_nm VARCHAR(20) NOT NULL,
	ct_gun_gu_nm VARCHAR(40) NOT NULL,
	up_myun_dong_nm VARCHAR(100) NOT NULL,
	CONSTRAINT pk_zngm_rdong PRIMARY KEY (rdong_cd)
);

-- 11. ZNGM_ST_NM_LST
CREATE TABLE hanarocms.zngm_st_nm_lst (
	ldong_cd VARCHAR(10) NOT NULL,
	st_nm_cd VARCHAR(12) NOT NULL,
	audit_id VARCHAR(15) NOT NULL,
	audit_dtm TIMESTAMP NOT NULL,
	st_nm VARCHAR(80) NOT NULL,
	eff_sta_dt VARCHAR(8) NOT NULL,
	eff_end_dt VARCHAR(8) NOT NULL,
	st_eng_nm VARCHAR(80),
	up_myun_dong_ser_num VARCHAR(2),
	up_myun_dong_cl_cd VARCHAR(1) NOT NULL,
	sup_st_cd VARCHAR(7),
	sup_st_nm VARCHAR(80),
	st_nm_chg_rsn_cd VARCHAR(1),
	CONSTRAINT pk_zngm_st_nm_lst PRIMARY KEY (ldong_cd, st_nm_cd)
);

-- 12. ZNGM_ZIP
CREATE TABLE hanarocms.zngm_zip (
	zip VARCHAR(6) NOT NULL,
	ser_num NUMERIC(15,0) NOT NULL,
	ct_pvc_nm VARCHAR(20) NOT NULL,
	ct_gun_gu_nm VARCHAR(40) NOT NULL,
	up_myun_dong_nm VARCHAR(100),
	larg_dlv_plc_nm VARCHAR(40),
	sta_main_house_num_ctt VARCHAR(40),
	sta_sub_house_num_ctt VARCHAR(40),
	end_main_house_num_ctt VARCHAR(40),
	end_sub_house_num_ctt VARCHAR(40),
	house_num_cl_cd VARCHAR(1),
	usable_yn VARCHAR(1) NOT NULL,
	audit_id VARCHAR(15) NOT NULL,
	audit_dtm TIMESTAMP NOT NULL,
	ct_pvc_addr_cd VARCHAR(2),
	ct_gun_gu_addr_cd VARCHAR(4),
	kt_dong_cd_mapp_yn VARCHAR(1),
	CONSTRAINT pk_zngm_zip PRIMARY KEY (zip, ser_num)
);
