#!/usr/bin/env python
'''Test network creation.

@author Brandon Heller (brandonh@stanford.edu)
'''

import unittest

from ripl.dctopo import FatTreeTopo

class testFatTreeTopo(unittest.TestCase):
    '''Test FatTreeTopo with varying k.'''

    @staticmethod
    def testCreateTopos():
        '''Create multiple topos.'''
        sizes = range(4, 10, 2)
        for k in sizes:
            FatTreeTopo(k)

    def testValidateTopos(self):
        '''Verify number of hosts, switches, and nodes at each layer.'''
        sizes = range(4, 6, 2)
        for k in sizes:
            ft = FatTreeTopo(k)

            hosts = (k ** 3) / 4
            self.assertEqual(len(ft.hosts()), hosts)
            switches = 5 * (k ** 2) / 4
            self.assertEqual(len(ft.switches()), switches)
            nodes = hosts + switches
            self.assertEqual(len(ft.nodes()), nodes)

            self.assertEqual(len(ft.layer_nodes(0)), (k ** 2) / 4)
            self.assertEqual(len(ft.layer_nodes(1)), (k ** 2) / 2)
            self.assertEqual(len(ft.layer_nodes(2)), (k ** 2) / 2)
            self.assertEqual(len(ft.layer_nodes(3)), (k ** 3) / 4)

            self.assertEqual(len(ft.links()), 3 * hosts)

    def testNodeID(self):
        '''Verify NodeID conversion in both directions.'''
        pairs = {(0, 0, 1): 0x000001,
                 (0, 1, 1): 0x000101,
                 (1, 0, 1): 0x010001}
        for a, b in pairs.iteritems():
            (x, y, z) = a
            self.assertEqual(FatTreeTopo.FatTreeNodeID(x, y, z).dpid, b)
            self.assertEqual(str(FatTreeTopo.FatTreeNodeID(dpid = b)), str(a))

    def testUpNodesAndEdges(self):
        '''Verify number of up edges at each layer.'''
        ft = FatTreeTopo(4)

        # map FatTreeNodeID inputs to down node/edge totals
        pairs = {(0, 0, 2): 1,
                 (0, 0, 1): 2,
                 (0, 2, 1): 2}
        for a, b in pairs.iteritems():
            (x, y, z) = a
            host = FatTreeTopo.FatTreeNodeID(x, y, z).name_str()
            self.assertEqual(len(ft.up_nodes(host)), b)
            self.assertEqual(len(ft.up_edges(host)), b)

    def testDownNodesAndEdges(self):
        '''Verify number of down edges at each layer.'''
        ft = FatTreeTopo(4)

        # map FatTreeNodeID inputs to down node/edge totals
        pairs = {(0, 0, 1): 2,
                 (0, 2, 1): 2,
                 (4, 1, 1): 4}
        for a, b in pairs.iteritems():
            (x, y, z) = a
            host = FatTreeTopo.FatTreeNodeID(x, y, z).name_str()
            self.assertEqual(len(ft.down_nodes(host)), b)
            self.assertEqual(len(ft.down_edges(host)), b)

    def testPorts(self):
        '''Verify port numbering between selected nodes.'''
        ft = FatTreeTopo(4)

        tuples = [((0, 0, 2), (0, 0, 1), 0, 2),
                  ((0, 0, 1), (0, 2, 1), 1, 2),
                  ((0, 0, 1), (0, 3, 1), 3, 2),
                  ((0, 2, 1), (4, 1, 1), 1, 1),
                  ((0, 2, 1), (4, 1, 2), 3, 1),
                  ((3, 3, 1), (4, 2, 1), 1, 4)
                  ]
        for tuple_ in tuples:
            src, dst, srcp_exp, dstp_exp = tuple_
            x, y, z = src
            x2, y2, z2 = dst
            src_dpid = FatTreeTopo.FatTreeNodeID(x, y, z).name_str()
            dst_dpid = FatTreeTopo.FatTreeNodeID(x2, y2, z2).name_str()
            (srcp, dstp) = ft.port(src_dpid, dst_dpid)
            self.assertEqual(srcp, srcp_exp)
            self.assertEqual(dstp, dstp_exp)
            # flip order and ensure same result
            (dstp, srcp) = ft.port(dst_dpid, src_dpid)
            self.assertEqual(srcp, srcp_exp)
            self.assertEqual(dstp, dstp_exp)


if __name__ == '__main__':
    unittest.main()
