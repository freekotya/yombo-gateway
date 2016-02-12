from yombo.ext.twistar.registry import Registry
from yombo.ext.twistar.dbconfig.base import InteractionBase


class SQLiteDBConfig(InteractionBase):
    def whereToString(self, where):
        assert(type(where) is list)
        query = where[0]
        args = where[1:]
        return (query, args)


    def updateArgsToString(self, args):
        colnames = self.escapeColNames(args.keys())
        setstring = ",".join([key + " = ?" for key in colnames])
        return (setstring, args.values())


    def insertArgsToString(self, vals):
        return "(" + ",".join(["?" for _ in vals.items()]) + ")"


    # retarded sqlite can't handle multiple row inserts
    def insertMany(self, tablename, vals):
        def _insertMany(txn):
            for val in vals:
                self.insert(tablename, val, txn)
        return Registry.DBPOOL.runInteraction(_insertMany)

    def pragma(self, pragma_string):
        """
        Truncate the given tablename.

        @return: A C{Deferred}.
        """
        q = "PRAGMA %s" % pragma_string
        return self.runInteraction(self._doselect, q, [], 'PRAGMA_table_info')
