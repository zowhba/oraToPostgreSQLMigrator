CREATE SCHEMA IF NOT EXISTS edmp;

CREATE TABLE edmp.um_upd_sw_dvc_ver_map (
    modl_cd VARCHAR(12) NOT NULL,
    modl_nm VARCHAR(64) NOT NULL,
    stb_sw_ver VARCHAR(30) NOT NULL,
    stb_sw_rst_ver VARCHAR(30),
    sw_id VARCHAR(12),
    sw_file_id VARCHAR(12),
    stm_fir_reg_date TIMESTAMP NOT NULL,
    stm_fir_reg_user_id VARCHAR(24) NOT NULL,
    stm_last_upd_date TIMESTAMP NOT NULL,
    stm_last_upd_user_id VARCHAR(24) NOT NULL,
    CONSTRAINT um_upd_sw_dvc_ver_map_pk 
        PRIMARY KEY (modl_nm, stb_sw_ver)
);

CREATE TABLE edmp.ad_user_mst (
    user_id VARCHAR(24) NOT NULL,
    user_nm VARCHAR(24) NOT NULL,
    user_pwd VARCHAR(128) NOT NULL,
    user_typ_fg_cd VARCHAR(2) NOT NULL,
    user_co_fg_cd VARCHAR(2) NOT NULL,
    user_email_addr VARCHAR(64),
    user_bf_pwd VARCHAR(128),
    user_pwd_last_upd_date TIMESTAMP,
    del_yn VARCHAR(1) NOT NULL DEFAULT 'N',
    use_yn VARCHAR(1) NOT NULL DEFAULT 'Y',
    user_login_last_date TIMESTAMP,
    user_id_lock_yn VARCHAR(1),
    login_fail_cnt NUMERIC(2,0),
    join_aprv_sts_cd VARCHAR(2),
    stm_fir_reg_date TIMESTAMP,
    stm_fir_reg_user_id VARCHAR(24),
    stm_last_upd_date TIMESTAMP,
    stm_last_upd_user_id VARCHAR(24),
    alrm_last_conf_date TIMESTAMP,
    init_menu_id VARCHAR(12),
    CONSTRAINT ad_user_mst_pk 
        PRIMARY KEY (user_id)
);

CREATE TABLE edmp.dm_dvc_mst (
    stb_id VARCHAR(40) NOT NULL,
    plan_id VARCHAR(30),
    exe_sch_id VARCHAR(12),
    stb_ui_ver VARCHAR(30),
    stb_sw_ver VARCHAR(30),
    stb_sw_plan_inst_ver VARCHAR(30),
    stb_sw_plan_last_ver VARCHAR(30),
    stb_sw_upd_date TIMESTAMP,
    err_cd VARCHAR(4),
    del_yn VARCHAR(1) NOT NULL DEFAULT 'N',
    use_yn VARCHAR(1) NOT NULL DEFAULT 'Y',
    stm_fir_reg_date TIMESTAMP,
    stm_fir_reg_user_id VARCHAR(24),
    stm_last_upd_date TIMESTAMP,
    stm_last_upd_user_id VARCHAR(24),
    team_cd VARCHAR(10),
    lock_yn VARCHAR(1) DEFAULT 'N',
    area1_cd VARCHAR(20),
    stb_last_conn_date TIMESTAMP,
    req_svc VARCHAR(20),
    hdmi_pow VARCHAR(1),
    rcu_pairing VARCHAR(1),
    rcu_manufr_cd VARCHAR(16),
    rcu_firm_ver VARCHAR(8),
    trigger_cd VARCHAR(2),
    stm_uptm TIMESTAMP,
    clnt_ipaddr VARCHAR(40),
    clnt_pub_ipaddr VARCHAR(40),
    native_ui_ver VARCHAR(30),
    web_ui_ver VARCHAR(30),
    upd_yn VARCHAR(1) NOT NULL DEFAULT 'Y',
    CONSTRAINT dm_dvc_mst_pk 
        PRIMARY KEY (stb_id)
);
