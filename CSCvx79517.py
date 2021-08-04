#!/usr/bin/python2.7
import subprocess
import sys
import logging
import logging.handlers
import threading
import json
import traceback
import time

logger = logging.getLogger(__name__)

svc_mo = {'bootmgr': 'actionBootmgrSubj', 'dbgr': 'actionDbgrSubj', 'domainmgr': 'actionDomainmgrSubj',
          'edmgr': 'actionEdmgrSubj', 'eventmgr': 'actionEventmgrSubj', 'idmgr': 'actionIdmgrSubj',
          'licensemgr': 'actionLicensemgrSubj', 'observer': 'actionObserverSubj',
          'plgnhandler': 'actionPlgnhandlerSubj',
          'policydist': 'actionPolicydistSubj', 'scripthandler': 'actionScripthandlerSubj',
          'policymgr': 'actionPolicymgrSubj', 'topomgr': 'actionTopomgrSubj', 'vmmmgr': 'actionVmmmgrSubj'}
action_mo = []

def setup_logger(logger, level):
    logging_level = {
        "debug": logging.DEBUG,
        "info": logging.INFO,
        "warn": logging.WARNING,
    }.get(level, logging.DEBUG)
    logger.setLevel(logging_level)
    logger_handler = logging.StreamHandler(sys.stdout)
    fmt = "%(asctime)s.%(msecs).03d||%(levelname)s||"
    fmt += "(%(lineno)d)||%(message)s"
    logger_handler.setFormatter(logging.Formatter(
        fmt=fmt,
        datefmt="%Z %Y-%m-%dT%H:%M:%S")
    )
    logger.addHandler(logger_handler)
    filehandler = logging.FileHandler('/data/techsupport/util.log')
    filehandler.setLevel(logging.DEBUG)
    filehandler.setFormatter(logging.Formatter(
        fmt=fmt,
        datefmt="%Z %Y-%m-%dT%H:%M:%S")
    )
    logger.addHandler(filehandler)


def get_cmd(cmd):
    """ return output of shell command, return None on error"""
    try:
        logger.debug("get_cmd: %s" % cmd)
        return subprocess.check_output(cmd, shell=True,
                                       stderr=subprocess.STDOUT)
    except subprocess.CalledProcessError as e:
        logger.warn("error executing command: %s" % e)
        return None


def pretty_print(js):
    """ try to convert json to pretty-print format """
    try:
        return json.dumps(js, indent=2, separators=(",", ":"))
    except Exception as e:
        print traceback.print_exc()
        return "%s" % js


def icurl(url, **kwargs):
    """ perform icurl for object/class based on relative dn and
        return json object.  Returns None on error
    """

    # default page size handler and timeouts
    page_size = kwargs.get("page_size", 75000)
    page = 0

    # build icurl command
    url_delim = "?"
    if "?" in url: url_delim = "&"

    # walk through pages until return count is less than page_size
    results = []
    while 1:
        turl = "%s%spage-size=%s&page=%s" % (url, url_delim, page_size, page)
        logger.debug("icurl: %s" % turl)
        tstart = time.time()
        try:
            resp = get_cmd("icurl -s 'http://127.0.0.1:7777/%s'" % turl)
        except Exception as e:
            logger.warn("exception occurred in get request: %s" % (
                traceback.format_exc()))
            return None
        logger.debug("response time: %f" % (time.time() - tstart))
        if resp is None:
            logger.warn("failed to get data: %s" % url)
            return None
        try:
            js = json.loads(resp)
            if "imdata" not in js or "totalCount" not in js:
                logger.error("failed to parse js reply: %s" % pretty_print(js))
                return None
            results += js["imdata"]
            logger.debug("results count: %s/%s %s" % (len(results), js["totalCount"],turl))
            if len(js["imdata"]) < page_size or \
                    len(results) >= int(js["totalCount"]):
                logger.debug("all pages received")
                return results
            page += 1
        except ValueError as e:
            logger.error("failed to decode resp: %s" % resp)
            return None
    return None


def build_query_filters(**kwargs):
    """
        queryTarget=[children|subtree]
        targetSubtreeClass=[mo-class]
        queryTargetFilter=[filter]
        rspSubtree=[no|children|full]
        rspSubtreeInclude=[attr]
        rspPropInclude=[all|naming-only|config-explicit|config-all|oper]
    """
    queryTarget = kwargs.get("queryTarget", None)
    targetSubtreeClass = kwargs.get("targetSubtreeClass", None)
    queryTargetFilter = kwargs.get("queryTargetFilter", None)
    rspSubtree = kwargs.get("rspSubtree", None)
    rspSubtreeInclude = kwargs.get("rspSubtreeInclude", None)
    rspSubtreeClass = kwargs.get("rspSubtreeClass", None)
    rspPropInclude = kwargs.get("rspPropInclude", None)
    opts = ""
    if queryTarget is not None:
        opts += "&query-target=%s" % queryTarget
    if targetSubtreeClass is not None:
        opts += "&target-subtree-class=%s" % targetSubtreeClass
    if queryTargetFilter is not None:
        opts += "&query-target-filter=%s" % queryTargetFilter
    if rspSubtree is not None:
        opts += "&rsp-subtree=%s" % rspSubtree
    if rspSubtreeInclude is not None:
        opts += "&rsp-subtree-include=%s" % rspSubtreeInclude
    if rspSubtreeClass is not None:
        opts += "&rsp-subtree-class=%s" % rspSubtreeClass
    if rspPropInclude is not None:
        opts += "&rsp-prop-include=%s" % rspPropInclude
    if len(opts) > 0: opts = "?%s" % opts.strip("&")
    return opts


def get_class(svc, classname, shard, **kwargs):
    # perform class query
    opts = build_query_filters(**kwargs)
    url = "/api/%s/class/%s.json%s?shard=%s" % (svc, classname, opts, shard)
    return icurl(url, **kwargs)


def batch_work(work):
    # work is list of tuples (target, args) that needs to be executed in parallel.
    # This function will execute each and wait until complete before returning
    threads = []
    for (target, args) in work:
        t = threading.Thread(target=target, args=args)
        t.daemon = True
        t.start()
        threads.append(t)
    for t in threads:
        t.join()
    return


def exam_action_pcons(svc, shard, classname):
    global action_mo
    action = get_class(svc, classname, shard)
    pcons = get_class(svc, "pconsRefDn", shard)

    for mo in action:
        pcons_ref_found = False
        if classname in mo:
            if "pcons/refcont" in mo[classname]["attributes"]["oDn"]:
                action_odn = mo[classname]["attributes"]["oDn"]
                for pmo in pcons:
                    if (mo[classname]["attributes"]["oDn"].startswith("pcons/refcont")) and ("pconsRefDn" in mo[classname]["attributes"]["oCl"]):
                        pcons_ref_found = True
                        break
                if pcons_ref_found is False:
                    action_mo.append("%s:%s"%(svc,shard))
                    action_mo.append(mo)

def start():
    work = []
    for svc in svc_mo:
        classname = svc_mo[svc]
        if svc == "policydist" or svc == "licensemgr":
            work.append((exam_action_pcons, (svc, "1", classname,)))
            continue
        else:
            for shard in range(1, 33):
                work.append((exam_action_pcons, (svc, shard, classname,)))
    if len(work) >= 1:
        batch_work(work)


if __name__ == "__main__":
    import argparse
    from argparse import RawTextHelpFormatter

    # input arguments from CLI
    desc = """
    Scan actionSubj Mo and find the matching pconsRefDn. If not found,list the actionSubj mo.
    """
    parser = argparse.ArgumentParser(description=desc, formatter_class=RawTextHelpFormatter)
    parser.add_argument("-d", dest="debug", choices=["debug", "info", "warn"], default="info")
    args = parser.parse_args()
    setup_logger(logger, args.debug)
    start()
    if len(action_mo) >= 1:
        logger.warn("One or More service has actionSubj mismatch with pconsRefDn")
        logger.info(pretty_print(action_mo))
    else:
        logger.info("There is no actionSubj and pconsRefDn mismatch found")
