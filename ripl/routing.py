#!/usr/bin/env python
'''@package routing

Routing engine base class.

@author Brandon Heller (brandonh@stanford.edu)
'''
from copy import copy
from random import choice

import logging
lg = logging.getLogger('ripl.routing')

DEBUG = False

lg.setLevel(logging.WARNING)
if DEBUG:
    lg.setLevel(logging.DEBUG)
    lg.addHandler(logging.StreamHandler())


class Routing(object):
    '''Base class for data center network routing.

    Routing engines must implement the get_route() method.
    '''

    def __init__(self, topo):
        '''Create Routing object.

        @param topo Topo object from Net parent
        '''
        self.topo = topo

    def get_route(self, src, dst, pkt):
        '''Return flow path.

        @param src source host
        @param dst destination host
        @param hash_ hash value

        @return flow_path list of DPIDs to traverse (including hosts)
        '''
        raise NotImplementedError


class StructuredRouting(Routing):
    '''Route flow through a StructuredTopo and return one path.

    Optionally accepts a function to choose among the set of valid paths.  For
    example, this could be based on a random choice, hash value, or
    always-leftmost path (yielding spanning-tree routing).

    Completely stupid!  Think of it as a topology-aware Dijstra's, that either
    extends the frontier until paths are found, or quits when it has looked for
    path all the way up to the core.  It simply enumerates all valid paths and
    chooses one.  Alternately, think of it as a bidrectional DFS.

    This is in no way optimized, and may be the slowest routing engine you've
    ever seen.  Still, it works with both VL2 and FatTree topos, and should
    help to bootstrap hardware testing and policy choices.

    The main data structures are the path dicts, one each for the src and dst.
    Each path dict has node ids as its keys.  The values are lists of routes,
    where each route records the list of dpids to get from the starting point
    (src or dst) to the key.

    Invariant: the last element in each route must be equal to the key.
    '''

    def __init__(self, topo, path_choice):
        '''Create Routing object.

        @param topo Topo object
        @param path_choice path choice function (see examples below)
        '''
        self.topo = topo
        self.path_choice = path_choice
        self.src_paths = None
        self.dst_paths = None
        self.src_path_layer = None
        self.dst_path_layer = None

    def _extend_reachable(self, frontier_layer):
        '''Extend reachability up, closer to core.

        @param frontier_layer layer we're extending TO, for filtering paths

        @return paths list of complete paths or None if no overlap
            invariant: path starts with src, ends in dst

        If extending the reachability frontier up yields a path to a node which
        already has some other path, then add that to a list to return of valid
        path choices.  If multiple paths lead to the newly-reached node, then
        add a path for every possible combination.  For this reason, beware
        exponential path explosion.

        Modifies most internal data structures as a side effect.
        '''

        complete_paths = [] # List of complete dpid routes

        # expand src frontier if it's below the dst
        if self.src_path_layer > frontier_layer:

            src_paths_next = {}
            # expand src frontier up
            for node in sorted(self.src_paths):

                src_path_list = self.src_paths[node]
                lg.info("src path list for node %s is %s" %
                        (node, src_path_list))
                if not src_path_list or len(src_path_list) == 0:
                    continue
                last = src_path_list[0][-1] # Last element on first list

                up_edges = self.topo.up_edges(last)
                if not up_edges:
                    continue
                assert up_edges
                up_nodes = self.topo.up_nodes(last)
                if not up_nodes:
                    continue
                assert up_nodes

                for edge in sorted(up_edges):
                    a, b = edge
                    assert a == last
                    assert b in up_nodes
                    frontier_node = b
                    # add path if it connects the src and dst
                    if frontier_node in self.dst_paths:
                        dst_path_list = self.dst_paths[frontier_node]
                        lg.info('self.dst_paths[frontier_node] = %s' %
                                self.dst_paths[frontier_node])
                        for dst_path in dst_path_list:
                            dst_path_rev = copy(dst_path)
                            dst_path_rev.reverse()
                            for src_path in src_path_list:
                                new_path = src_path + dst_path_rev
                                lg.info('adding path: %s' % new_path)
                                complete_paths.append(new_path)
                    else:
                        if frontier_node not in src_paths_next:
                            src_paths_next[frontier_node] = []
                        for src_path in src_path_list:
                            extended_path = src_path + [frontier_node]
                            src_paths_next[frontier_node].append(extended_path)
                            lg.info("adding to self.paths[%s] %s: " % \
                                      (frontier_node, extended_path))

            # filter paths to only those in the most recently seen layer
            lg.info("src_paths_next: %s" % src_paths_next)
            self.src_paths = src_paths_next
            self.src_path_layer -= 1

        # expand dst frontier if it's below the rc
        if self.dst_path_layer > frontier_layer:

            dst_paths_next = {}
            # expand src frontier up
            for node in self.dst_paths:

                dst_path_list = self.dst_paths[node]
                lg.info("dst path list for node %s is %s" %
                        (node, dst_path_list))
                last = dst_path_list[0][-1] # last element on first list

                up_edges = self.topo.up_edges(last)
                if not up_edges:
                    continue
                assert up_edges
                up_nodes = self.topo.up_nodes(last)
                if not up_nodes:
                    continue
                assert up_nodes
                lg.info("up_edges = %s" % sorted(up_edges))
                for edge in sorted(up_edges):
                    a, b = edge
                    assert a == last
                    assert b in up_nodes
                    frontier_node = b
                    # add path if it connects the src and dst
                    if frontier_node in self.src_paths:
                        src_path_list = self.src_paths[frontier_node]
                        lg.info('self.src_paths[frontier_node] = %s' %
                                self.src_paths[frontier_node])
                        for src_path in src_path_list:
                            for dst_path in dst_path_list:
                                dst_path_rev = copy(dst_path)
                                dst_path_rev.reverse()
                                new_path = src_path + dst_path_rev
                                lg.info('adding path: %s' % new_path)
                                complete_paths.append(new_path)

                    else:
                        if frontier_node not in dst_paths_next:
                            dst_paths_next[frontier_node] = []
                        for dst_path in dst_path_list:
                            extended_path = dst_path + [frontier_node]
                            dst_paths_next[frontier_node].append(extended_path)
                            lg.info("adding to self.paths[%s] %s: " % \
                                      (frontier_node, extended_path))

            # filter paths to only those in the most recently seen layer
            lg.info("dst_paths_next: %s" % dst_paths_next)
            self.dst_paths = dst_paths_next
            self.dst_path_layer -= 1

        lg.info("complete paths = %s" % complete_paths)
        return complete_paths

    def get_route(self, src, dst, hash_):
        '''Return flow path.

        @param src source dpid (for host or switch)
        @param dst destination dpid (for host or switch)
        @param hash_ hash value

        @return flow_path list of DPIDs to traverse (including inputs), or None
        '''

        if src == dst:
          return [src]

        self.src_paths = {src: [[src]]}
        self.dst_paths = {dst: [[dst]]}

        src_layer = self.topo.layer(src)
        dst_layer = self.topo.layer(dst)

        # use later in extend_reachable
        self.src_path_layer = src_layer
        self.dst_path_layer = dst_layer

        # the lowest layer is the one closest to hosts, with the highest value
        lowest_starting_layer = src_layer
        if dst_layer > src_layer:
            lowest_starting_layer = dst_layer

        for depth in range(lowest_starting_layer - 1, -1, -1):
            lg.info('-------------------------------------------')
            paths_found = self._extend_reachable(depth)
            if paths_found:
                path_choice = self.path_choice(paths_found, src, dst, hash_)
                lg.info('path_choice = %s' % path_choice)
                return path_choice
        return None

# Disable unused argument warnings in the classes below
# pylint: disable-msg=W0613


class STStructuredRouting(StructuredRouting):
    '''Spanning Tree Structured Routing.'''

    def __init__(self, topo):
        '''Create StructuredRouting object.

        @param topo Topo object
        '''

        def choose_leftmost(paths, src, dst, hash_):
            '''Choose leftmost path

            @param path paths of dpids generated by a routing engine
            @param src src dpid (unused)
            @param dst dst dpid (unused)
            @param hash_ hash value (unused)
	    '''
            return paths[0]

        super(STStructuredRouting, self).__init__(topo, choose_leftmost)


class RandomStructuredRouting(StructuredRouting):
    '''Random Structured Routing.'''

    def __init__(self, topo):
        '''Create StructuredRouting object.

        @param topo Topo object
        '''

        def choose_random(paths, src, dst, hash_):
            '''Choose random path

            @param path paths of dpids generated by a routing engine
            @param src src dpid (unused)
            @param dst dst dpid (unused)
            @param hash_ hash value (unused)
            '''
            return choice(paths)

        super(RandomStructuredRouting, self).__init__(topo, choose_random)


class HashedStructuredRouting(StructuredRouting):
    '''Hashed Structured Routing.'''

    def __init__(self, topo):
        '''Create StructuredRouting object.

        @param topo Topo object
        '''

        def choose_hashed(paths, src, dst, hash_):
            '''Choose consistent hashed path

            @param path paths of dpids generated by a routing engine
            @param src src dpid
            @param dst dst dpid
            @param hash_ hash value
            '''
            choice = hash_ % len(paths)
            path = sorted(paths)[choice]
            return path

        super(HashedStructuredRouting, self).__init__(topo, choose_hashed)
# pylint: enable-msg=W0613
