class DBValue():
    def __init__(self, data):
        self.bucket_time, self.bucket_size, self.bucket_name, self.bucket_value, self.bucket_type = data
        self.bucket_time = int(self.bucket_time)
        self.bucket_size = int(self.bucket_size)
        self.bucket_value = float(self.bucket_value)
    
    @classmethod
    def from_db_string(cls, db_string):
        FIELD_NUMBER = 5
        fields = db_string.split("|")
        if len(fields) != FIELD_NUMBER:
            raise ValueError("{} fields expected, but got {}".format(FIELD_NUMBER, len(fields)))
        return cls(fields)
    
    def __str__(self):
        fieldnames = ["bucket_time", "bucket_size", "bucket_name", "bucket_value", "bucket_type"]
        fields = [self.bucket_time, self.bucket_size, self.bucket_name, self.bucket_value, self.bucket_type]
        return "\n".join(["{db value"] + ["{}: {}".format(fieldname, field) for field, fieldname in zip(fields, fieldnames)] + ["}"])