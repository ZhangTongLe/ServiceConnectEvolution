# -*- coding: UTF-8 -*-
"""
# ******************************************************
# * author: "Talen Hao(天飞)<talenhao@gmail.com>"      *
# ******************************************************
"""
# todo menu

import traceback
import re
import pickle

import networkx as nx
import networkx.algorithms.traversal as nx_a_t
import networkx.drawing as nxd

from serconevo.model import db_connect
from serconevo.agent.service_collect_agent import script_head
from serconevo.agent.service_collect_agent import db_close
from serconevo.agent.service_collect_agent import spend_time
from serconevo.agent.service_collect_agent import start_end_point

# for log >>
import logging
import os
from serconevo.log4p import log4p

SCRIPT_NAME = os.path.basename(__file__)
pLogger = log4p.GetLogger(SCRIPT_NAME, logging.DEBUG).get_l()
# log end <<


identify_line = "=*=" * 10

db_con = db_connect.DbInitConnect()
config_parser = db_con.python_config_parser
service_listens_table = config_parser.get("TABLE", "listen_table")
service_connections_table = config_parser.get("TABLE", "connection_table")


def db_fetchall(sql_cmd, fetch='all'):
    """
    execute sql_cmd, if no set fetch arg, default return 10 results;
    if set fetch arg, it can be set 'one' or 'all'.
    :param sql_cmd:
    :param fetch:
    :return:
    """
    pLogger.debug("SQL_CMD is =====> {!r}  __________".format(sql_cmd))
    db_con.cursor.execute(sql_cmd)
    pLogger.info("=====> DB operation command result: {!r}".format(db_con.cursor.rowcount))
    if fetch == 'one':
        return db_con.cursor.fetchone()
    elif fetch == "all":
        return db_con.cursor.fetchall()
    else:
        return db_con.cursor.fetchmany(size=10)


def match_sort(project, string):
    re_compile = re.compile(r'=(/[-\w]+){1,5}\b')
    re_findall = re_compile.search(string)
    pLogger.debug("re_findall: {!r}".format(re_findall))
    try:
        find_one = re_findall.group(0)
    except AttributeError:
        pLogger.debug("{} has no re compile!! It is : \n{}".format(project, string))
        return string
    else:
        pLogger.debug("find_one is : {!r}".format(find_one))
        return find_one


def node_match(name, cwd=None, cmdline=None):
    """
    process P_name, cmdline maybe any string list;
    you cat assign some node name use p_name or use a short identify.
    :param name:
    :param cwd:
    :param cmdline:
    :return:
    """
    drop_list = ['ssh', 'sshd', 'whois', 'sshd']
#    from_drop_list = ['ssh', 'sshd', 'whois']
#    target_drop_list = ['sshd']
#    if flag == 'f':
#        drop_list = from_drop_list
#    elif flag == "t":
#        drop_list = target_drop_list
    pLogger.debug("param: {}, {}, {}".format(name, cwd, cmdline))
    name_list = ['zabbix_server']
    if name in drop_list:
        return "drop"
    elif name == 'java':
        node = match_sort('java', name + "=" + cwd)
        return node
    elif name in name_list:
        node = name
        return node
    else:
        node = ' '.join(eval(cmdline)[:3])  # rename p_cmdline just use 3 field
        return node


def get_relation_list_from_db():
    """
    ip v,port v: connection match listen
    ip v,port x: listen program exit after collect connections
    ip x,port v: this explains nothing
    ip x,port x: this is a out server
    :return:
    fetch_list
    """
    fetch_list = []
    now_process_num = 0
    # has listen program
    # step1, from node process
    connections_sql_cmd = "SELECT c.c_ip, c.c_port, c.p_name, c.p_cwd, c.p_cmdline, c.p_pid, c.flag " \
                          "FROM {} c" \
        .format(service_connections_table)
    connections_fetchall = db_fetchall(connections_sql_cmd, fetch='all')
    pLogger.debug("connections fetch is: {}".format(connections_fetchall))
    for connection in connections_fetchall:
        now_process_num += 1
        pLogger.info("Now process No. => {!r}".format(now_process_num))
        c_c_ip = connection[0]
        c_c_port = connection[1]
        c_p_name = connection[2]
        c_p_cwd = connection[3]
        c_p_cmdline = connection[4]
        c_id = connection[5]
        flag = connection[6]
        pLogger.debug("\n{0}\nprocess id {3}"
                      "\n{0}\nconnection is {1!r}, type: {2!r}, with flag {4!r}, type(flag)=> {5!r}"
                      .format(identify_line,
                              connection,
                              type(c_p_cmdline),
                              c_id,
                              flag,
                              type(flag)
                              )
                      )
        # name_node = ' '.join(eval(c_p_cmdline))  # c.p_cmdline
        name_node = c_p_cmdline
        n_result = node_match(c_p_name, cwd=c_p_cwd, cmdline=c_p_cmdline)

        # ip node convert
        match_listen_sql_cmd = "select L.l_ip, L.l_port, L.p_cmdline, L.p_cwd, L.p_name from {} L" \
                               " where L.l_ip = {!r} and L.l_port = {!r}" \
            .format(service_listens_table, c_c_ip, c_c_port)
        match_listen = db_fetchall(match_listen_sql_cmd, fetch='one')
        pLogger.debug("match_listen_result: {!r}".format(match_listen))
        if match_listen:
            pLogger.debug("match_listen is : {}".format(match_listen))
            # 取出target的程序命令行
            l_p_cmdline = match_listen[2]
            l_p_cwd = match_listen[3]
            l_p_name = match_listen[4]
            pLogger.debug("target_node: {}, {}, {}".format(l_p_name, l_p_cwd, l_p_cmdline))
            convert_node = l_p_cmdline
            c_result = node_match(l_p_name, cwd=l_p_name, cmdline=l_p_cmdline)
        else:
            # convert_node = c_c_ip + ':' + c_c_port
            convert_node = c_c_ip
            c_result = convert_node
            pLogger.debug("convert_node with port {!r}".format(c_c_ip + ':' + c_c_port))
        pLogger.debug("convert_node=>{!r}, c_result=>{!r}".format(convert_node, c_result))
        if n_result == "drop" or c_result == 'drop':
            pLogger.warn("process {} has connection {} are not needed, drop.".format(name_node, convert_node))
            pLogger.debug("drop item is : {}".format(connection))
            continue
        else:
            if flag == 1:
                from_node = n_result
                target_node = c_result
            elif flag == 0:
                from_node = c_result
                target_node = n_result
            else:
                pLogger.error("flag is needed!")
                continue
        # finally from_node, target_node
        pLogger.debug("{}\nfrom_node :{!r} \ntarget_node: {!r}".format(identify_line, from_node, target_node))
        fetch_list.append((from_node.strip(), target_node.strip()))
    pLogger.debug("{}\nfetch_list is :\n {!r}".format(identify_line, fetch_list))
    with open('fetch_list.bin', 'wb') as dump_file:
        pickle.dump(fetch_list, dump_file, True)
    return fetch_list


def gv_graph(nxg, filename, node_name=None, fmt='png'):
    # save a dot file to local disk
    nxd.nx_agraph.write_dot(nxg, "dot/" + filename + '.dot')
    # convert to pygraphviz agraph object
    pgv_graph = nxd.nx_agraph.to_agraph(nxg)
    pgv_graph.graph_attr.update(rankdir="LR")
    pgv_graph.node_attr.update(fillcolor='green:yellow',
                               style='filled',
                               shape='polygon',
                               # orientation='rotate',
                               orientation='landscape',
                               ratio='compress',
                               fontsize='8',
                               remincross='true',
                               concentrate='false',
                               compound='true',
                               overlap='false',
                               rank='source',
                               constraint='false',
                               clusterrank='none',
                               center='false',
                               imagepos='ml',
                               decorate='true',
                               fixedsize='false',
                               height='.1'
                               )
    pgv_graph.edge_attr.update(splines='compound', concentrate='true')
    if node_name:
        pgv_graph.add_node(node_name, fillcolor='red:yellow', shape='octagon', style='filled',
                           # gradientangle='90',
                           fontsize=10, labeljust='l',
                           height='.1')
    else:
        pLogger.warning("No center node.")
    pgv_graph.draw("img/" + filename + '.' + fmt, format=fmt, prog='dot')


def graph_dot(node_list):
    # create directed graph
    # g = nx.MultiDiGraph(day="Friday")
    g = nx.DiGraph(name='all')
    pLogger.debug("g.DiGraph is: {!r}".format(g.graph))
    g.add_edges_from(node_list)
    pLogger.debug("g.node : {!r}".format(g.node))
    pLogger.debug("g.nodes: {!r}\ng.edges: {!r}".format(g.nodes(), g.edges()))
    pLogger.debug("nos: {}".format(g.number_of_selfloops()))
    # dfs
    return g


def draw_node(graph):
    g = graph
    for source_node in g.node:
        dfs_edges_result = nx_a_t.dfs_edges(g, source=source_node)
        gr = g.reverse(copy=True)
        gr_dfs_edges_result = nx_a_t.dfs_edges(gr, source=source_node)

        # gv_graph(gr, filename='gr')
        follows = list(dfs_edges_result)
        leaders = list(gr_dfs_edges_result)
        pLogger.debug("\nfollows type{}: {}\ntype {} leaders: {}".format(
            type(follows), follows, type(leaders), leaders))
        gr_new = nx.DiGraph(name='gr')
        gr_new.add_edges_from(leaders)
        pLogger.debug(gr_new.graph)
        g_new = gr_new.reverse(copy=True)
        g_new.add_edges_from(follows)
        pLogger.debug(g_new.graph)
        # draw a graph
        gv_graph(g_new,
                 filename=source_node.replace(' ', '-').replace('/', '_').replace('=', ''),
                 node_name=source_node)


def draw_all(graph):
    gv_graph(graph, filename='all')


@spend_time
@start_end_point(SCRIPT_NAME)
@script_head
@db_close
def main():
    try:
        edges_list = get_relation_list_from_db()
    except:
        traceback.print_exc()
    else:
        gv = graph_dot(edges_list)
        draw_node(gv)
        draw_all(gv)


if __name__ == "__main__":
    main()
